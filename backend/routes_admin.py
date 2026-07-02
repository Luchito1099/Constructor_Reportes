"""Panel de administración: gestionar roles de usuarios (solo admin)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from auth import FEATURES, require_admin
from db import User, get_session

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserRow(BaseModel):
    id: int
    email: str
    role: str
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    role: str  # "admin" | "viewer"


class PermsUpdate(BaseModel):
    permissions: list[str]


def _row(u: User) -> UserRow:
    try:
        perms = json.loads(u.permissions or "[]")
    except (ValueError, TypeError):
        perms = []
    return UserRow(id=u.id, email=u.email, role=u.role, permissions=perms)


@router.get("/features")
def features(admin: User = Depends(require_admin)) -> list[str]:
    return FEATURES


@router.get("/users", response_model=list[UserRow])
def list_users(admin: User = Depends(require_admin),
               session: Session = Depends(get_session)) -> list[UserRow]:
    users = session.exec(select(User).order_by(User.id)).all()
    return [_row(u) for u in users]


@router.put("/users/{user_id}/permissions", response_model=UserRow)
def set_permissions(user_id: int, body: PermsUpdate,
                    admin: User = Depends(require_admin),
                    session: Session = Depends(get_session)) -> UserRow:
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    perms = [p for p in body.permissions if p in FEATURES]
    target.permissions = json.dumps(perms)
    session.add(target)
    session.commit()
    session.refresh(target)
    return _row(target)


@router.put("/users/{user_id}/role", response_model=UserRow)
def set_role(user_id: int, body: RoleUpdate,
             admin: User = Depends(require_admin),
             session: Session = Depends(get_session)) -> UserRow:
    if body.role not in ("admin", "viewer"):
        raise HTTPException(400, "Rol inválido")
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    # No permitir quedarse sin ningún admin
    if target.role == "admin" and body.role == "viewer":
        admins = session.exec(select(User).where(User.role == "admin")).all()
        if len(admins) <= 1:
            raise HTTPException(400, "Debe quedar al menos un administrador")
    target.role = body.role
    session.add(target)
    session.commit()
    session.refresh(target)
    return _row(target)


@router.delete("/users/{user_id}")
def delete_user(user_id: int,
                admin: User = Depends(require_admin),
                session: Session = Depends(get_session)) -> dict:
    if user_id == admin.id:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta")
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    session.delete(target)
    session.commit()
    return {"ok": True}
