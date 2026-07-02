"""Rutas de autenticación: registro, login, logout, quién soy."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import Session

from sqlmodel import select

from auth import (
    current_user,
    get_user_by_email,
    hash_password,
    set_session_cookie,
    clear_session_cookie,
    verify_password,
)
from config import ALLOW_REGISTER
from db import Catalog, User, get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str = "viewer"
    permissions: list[str] = []


def _perms(user: User) -> list[str]:
    import json
    try:
        return json.loads(user.permissions or "[]")
    except (ValueError, TypeError):
        return []


DEFAULT_CATALOG = {
    "gerencias": ["Lima Centro", "Lima Este", "Lima Oeste", "Lima Norte",
                  "Lima Sur", "NCH", "Mayoristas", "ON", "Campeones"],
    "brandpacks": ["Brandpack Lager", "Brandpack Oscura", "Brandpack Light"],
    "combos": ["Combo Familiar", "Combo Fiesta"],
    "materiales": ["Cerveza Lager 355ml", "Cerveza Lager 1L"],
    "zonas": ["Zona Metropolitana", "Zona Bajío"],
    "promos": ["2x1 Fin de Semana", "Descuento Mayoreo"],
    "tablas": ["ventas.fact_ventas", "ventas.fact_visita", "dim.cliente"],
    "columnas": ["id_cliente", "fecha", "unidades", "importe", "nombre_gerencia"],
}


@router.post("/register", response_model=UserOut)
def register(
    creds: Credentials,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    if not ALLOW_REGISTER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registro cerrado")
    if "@" not in creds.email or "." not in creds.email.split("@")[-1]:
        raise HTTPException(422, "Correo inválido")
    if get_user_by_email(session, creds.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese correo ya existe")
    if len(creds.password) < 6:
        raise HTTPException(422, "La contraseña debe tener al menos 6 caracteres")
    # El primer usuario del sistema queda admin; el resto, viewer.
    has_admin = session.exec(select(User).where(User.role == "admin")).first()
    role = "viewer" if has_admin else "admin"
    user = User(email=creds.email, password_hash=hash_password(creds.password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    # catálogo inicial solo para el admin (banco compartido)
    if role == "admin":
        import json
        session.add(Catalog(user_id=user.id, data_json=json.dumps(DEFAULT_CATALOG, ensure_ascii=False)))
        session.commit()
    set_session_cookie(response, user.id)
    return UserOut(id=user.id, email=user.email, role=user.role, permissions=_perms(user))


@router.post("/login", response_model=UserOut)
def login(
    creds: Credentials,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    user = get_user_by_email(session, creds.email)
    if not user or not verify_password(creds.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    set_session_cookie(response, user.id)
    return UserOut(id=user.id, email=user.email, role=user.role, permissions=_perms(user))


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, role=user.role, permissions=_perms(user))
