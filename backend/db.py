"""Modelos SQLModel y arranque de la base SQLite.

Todo se guarda por usuario. Las estructuras flexibles (parámetros de una query,
piezas de un notebook, ensamblado de un reporte) se guardan como JSON en texto
para no atarnos a un esquema rígido mientras el producto evoluciona.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine

from config import DATABASE_URL


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: str = "viewer"          # "admin" | "viewer"
    permissions: str = "[]"       # funciones habilitadas a un viewer (JSON: reportes/solicitudes/links/ia)
    created_at: datetime = Field(default_factory=_now)


class Query(SQLModel, table=True):
    """Una query del banco (o una plantilla de notebook multi-KPI)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    category: str = ""
    subcase: str = ""
    name: str = ""
    type: str = "query"           # "query" | "notebook"
    sql: str = ""
    params_json: str = "{}"       # valores rápidos guardados por parámetro
    extra_json: str = "{}"        # kpis/assembly/finalTable/viz para notebooks
    position: int = 0
    updated_at: datetime = Field(default_factory=_now)


class NotebookTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str = ""
    description: str = ""
    structure_json: str = "{}"    # piezas / layout del rompecabezas
    updated_at: datetime = Field(default_factory=_now)


class OutputBlock(SQLModel, table=True):
    """Bloque de salida reutilizable: código Python de PDF/Excel/correo/imagen."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str = ""
    kind: str = "pdf"             # pdf | excel | email | image | otro
    code: str = ""
    updated_at: datetime = Field(default_factory=_now)


class Report(SQLModel, table=True):
    """Un reporte ensamblado (el rompecabezas ya armado)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str = ""
    assembly_json: str = "{}"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ScheduledReport(SQLModel, table=True):
    """Un reporte de la agenda diaria (módulo Reportes por horario)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str = ""
    type: str = "corte"              # corte | acumulado | cierre | adhoc
    time: str = "08:00"             # HH:MM
    gerencias_json: str = "[]"       # lista de ids de gerencia
    channel: str = "whatsapp"       # whatsapp | email | both
    color: str = "blue"
    done: bool = False
    done_date: str = ""             # 'YYYY-MM-DD' del día en que se marcó (reseteo diario)
    position: int = 0
    updated_at: datetime = Field(default_factory=_now)


class Request(SQLModel, table=True):
    """Una solicitud/cambio pedido por la jefa (módulo Historial de pedidos)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    fecha_solicitud: str = ""        # 'YYYY-MM-DD'
    descripcion: str = ""
    prioridad: str = "media"        # alta | media | baja
    periodo: str = ""               # 'fin de mes' | 'semanal' | texto libre
    fecha_limite: str = ""          # 'YYYY-MM-DD' opcional
    notas: str = ""
    adjunto_link: str = ""
    adjunto_file: str = ""          # nombre del archivo subido (en uploads/<user_id>/)
    images_json: str = "[]"          # lista de capturas/imágenes como data URLs
    archivado: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Link(SQLModel, table=True):
    """Un enlace guardado (BI, herramientas, etc.) del banco compartido."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str = ""
    url: str = ""
    description: str = ""
    position: int = 0
    updated_at: datetime = Field(default_factory=_now)


class Catalog(SQLModel, table=True):
    """Catálogo por usuario (gerencias, brandpacks, zonas, columnas...) en JSON."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, unique=True, foreign_key="user.id")
    data_json: str = "{}"
    updated_at: datetime = Field(default_factory=_now)


engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_columns()
    _bootstrap_admin()


# Migración ligera para SQLite: create_all NO agrega columnas a tablas que ya
# existen, así que añadimos las nuevas a mano si faltan.
_MIGRATIONS = {
    "request": [("images_json", "TEXT DEFAULT '[]'")],
    "user": [("role", "TEXT DEFAULT 'viewer'"), ("permissions", "TEXT DEFAULT '[]'")],
}


def _bootstrap_admin() -> None:
    """Si no hay ningún admin, promueve al usuario más antiguo (id más bajo).
    Así la cuenta ya existente queda admin sin perder datos."""
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            has_admin = conn.execute(
                text("SELECT 1 FROM user WHERE role='admin' LIMIT 1")
            ).first()
            if has_admin:
                return
            first = conn.execute(
                text("SELECT id FROM user ORDER BY id LIMIT 1")
            ).first()
            if first:
                conn.execute(
                    text("UPDATE user SET role='admin' WHERE id=:i"), {"i": first[0]}
                )
                conn.commit()
        except Exception:
            pass


def _ensure_columns() -> None:
    from sqlalchemy import text
    with engine.connect() as conn:
        for table, cols in _MIGRATIONS.items():
            try:
                existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            except Exception:
                continue
            if not existing:  # la tabla aún no existe
                continue
            for name, decl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))
        conn.commit()


def get_session() -> Session:  # dependencia FastAPI
    with Session(engine) as session:
        yield session
