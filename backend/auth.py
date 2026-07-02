"""Autenticación: hash de contraseña + sesión por cookie firmada.

Usamos una cookie firmada con `itsdangerous` (no un JWT) por simplicidad: la
cookie contiene el id de usuario firmado; el servidor la verifica en cada
request. Sin estado extra en la base.
"""
from __future__ import annotations

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import Session, select

from config import (
    COOKIE_SECURE,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    SESSION_SECRET,
)
from db import User, get_session

_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="rb-session")


def _pw_bytes(raw: str) -> bytes:
    # bcrypt sólo admite hasta 72 bytes; truncamos de forma segura.
    return raw.encode("utf-8")[:72]


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_pw_bytes(raw), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(raw), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def set_session_cookie(response: Response, user_id: int) -> None:
    token = _serializer.dumps({"uid": user_id})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _uid_from_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid")
    return int(uid) if uid is not None else None


def current_user(
    session: Session = Depends(get_session),
    rb_session: str | None = Cookie(default=None),
) -> User:
    """Dependencia: exige sesión válida o lanza 401."""
    uid = _uid_from_token(rb_session)
    if uid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")
    user = session.get(User, uid)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    """Dependencia: exige rol admin o lanza 403 (para escrituras y recursos admin)."""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere permisos de administrador")
    return user


# Funciones que un admin puede habilitar a un viewer.
FEATURES = ["reportes", "solicitudes", "links", "ia"]


def has_perm(user: User, key: str) -> bool:
    """El admin tiene todo; un viewer solo lo que se le habilitó."""
    if user.role == "admin":
        return True
    import json
    try:
        return key in json.loads(user.permissions or "[]")
    except (ValueError, TypeError):
        return False


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()
