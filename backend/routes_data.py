"""CRUD por usuario del banco de queries, plantillas, bloques de salida,
reportes y catálogo. Todo filtrado por el usuario de la sesión."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Type

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from auth import current_user, has_perm, require_admin
from db import (
    Catalog,
    Link,
    NotebookTemplate,
    OutputBlock,
    Query,
    Report,
    Request,
    ScheduledReport,
    User,
    get_session,
)

router = APIRouter(prefix="/api", tags=["data"])


def _dump(obj: SQLModel) -> dict:
    d = obj.model_dump()
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _touch(obj: SQLModel) -> None:
    if hasattr(obj, "updated_at"):
        obj.updated_at = datetime.now(timezone.utc)


# Campos que el cliente puede escribir por modelo (nunca id/user_id).
WRITABLE = {
    Query: {"category", "subcase", "name", "type", "sql", "context",
            "params_json", "extra_json", "position"},
    NotebookTemplate: {"name", "description", "structure_json"},
    OutputBlock: {"name", "kind", "code"},
    Report: {"name", "assembly_json"},
    ScheduledReport: {"name", "type", "time", "gerencias_json", "channel",
                      "color", "done", "done_date", "position"},
    Request: {"fecha_solicitud", "descripcion", "prioridad", "periodo",
              "fecha_limite", "notas", "adjunto_link", "adjunto_file",
              "images_json", "archivado"},
    Link: {"name", "url", "description", "position"},
}


def _admin_ids(session: Session) -> list[int]:
    return list(session.exec(select(User.id).where(User.role == "admin")).all())


def _make_crud(model: Type[SQLModel], path: str, order,
               shared: bool = False, perm: str | None = None):
    """Genera list/create/update/delete para un modelo.

    - Escrituras (POST/PUT/DELETE): siempre requieren admin.
    - Lecturas (GET):
        · ``shared``     → cualquier autenticado ve el banco de los admins.
        · ``perm``       → lo ven admin o viewers con esa función habilitada
                           (devuelve el banco compartido de los admins).
        · ninguno        → solo el admin ve sus propios items.
    """

    if shared:
        @router.get(f"/{path}")
        def list_items(user: User = Depends(current_user),
                       session: Session = Depends(get_session)) -> list[dict]:
            ids = _admin_ids(session)
            stmt = select(model).where(model.user_id.in_(ids)).order_by(order)
            return [_dump(x) for x in session.exec(stmt).all()]
    elif perm:
        @router.get(f"/{path}")
        def list_items(user: User = Depends(current_user),
                       session: Session = Depends(get_session)) -> list[dict]:
            if not has_perm(user, perm):
                raise HTTPException(403, "Función no habilitada para tu usuario")
            ids = _admin_ids(session)
            stmt = select(model).where(model.user_id.in_(ids)).order_by(order)
            return [_dump(x) for x in session.exec(stmt).all()]
    else:
        @router.get(f"/{path}")
        def list_items(user: User = Depends(require_admin),
                       session: Session = Depends(get_session)) -> list[dict]:
            stmt = select(model).where(model.user_id == user.id).order_by(order)
            return [_dump(x) for x in session.exec(stmt).all()]

    @router.post(f"/{path}")
    def create_item(payload: dict[str, Any],
                    user: User = Depends(require_admin),
                    session: Session = Depends(get_session)) -> dict:
        data = {k: v for k, v in payload.items() if k in WRITABLE[model]}
        obj = model(user_id=user.id, **data)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return _dump(obj)

    @router.put(f"/{path}/{{item_id}}")
    def update_item(item_id: int, payload: dict[str, Any],
                    user: User = Depends(require_admin),
                    session: Session = Depends(get_session)) -> dict:
        obj = session.get(model, item_id)
        # admin puede editar cualquier item del banco compartido; en no-compartido, el suyo
        if not obj or (not shared and not perm and obj.user_id != user.id):
            raise HTTPException(404, "No encontrado")
        for k, v in payload.items():
            if k in WRITABLE[model]:
                setattr(obj, k, v)
        _touch(obj)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return _dump(obj)

    @router.delete(f"/{path}/{{item_id}}")
    def delete_item(item_id: int,
                    user: User = Depends(require_admin),
                    session: Session = Depends(get_session)) -> dict:
        obj = session.get(model, item_id)
        if not obj or (not shared and not perm and obj.user_id != user.id):
            raise HTTPException(404, "No encontrado")
        session.delete(obj)
        session.commit()
        return {"ok": True}


# Banco compartido (lo ven todos, lo escribe el admin):
_make_crud(Query, "queries", Query.position, shared=True)
_make_crud(Link, "links", Link.position, perm="links")
# Módulos habilitables por permiso (los ve admin o viewers con la función):
_make_crud(ScheduledReport, "scheduled-reports", ScheduledReport.time, perm="reportes")
_make_crud(Request, "requests", Request.created_at.desc(), perm="solicitudes")
# Internos del notebook, solo admin:
_make_crud(NotebookTemplate, "templates", NotebookTemplate.name)
_make_crud(OutputBlock, "output-blocks", OutputBlock.name)
_make_crud(Report, "reports", Report.created_at)


# --- Catálogo (compartido: el del admin) -------------------------------------
@router.get("/catalog")
def get_catalog(user: User = Depends(current_user),
                session: Session = Depends(get_session)) -> dict:
    ids = _admin_ids(session)
    cat = session.exec(
        select(Catalog).where(Catalog.user_id.in_(ids))
    ).first() if ids else None
    return json.loads(cat.data_json) if cat else {}


@router.put("/catalog")
def put_catalog(payload: dict[str, Any],
                user: User = Depends(require_admin),
                session: Session = Depends(get_session)) -> dict:
    cat = session.exec(select(Catalog).where(Catalog.user_id == user.id)).first()
    if not cat:
        cat = Catalog(user_id=user.id)
    cat.data_json = json.dumps(payload, ensure_ascii=False)
    _touch(cat)
    session.add(cat)
    session.commit()
    return payload
