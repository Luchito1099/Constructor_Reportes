"""Configuración central del backend.

Todo lo sensible (secreto de sesión, API keys de IA) se lee de variables de
entorno para que NUNCA quede escrito en el código ni viaje al navegador.
Puedes definirlas en un archivo `.env` (ver `.env.example`) o en el sistema.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def _load_dotenv() -> None:
    """Carga un `.env` sencillo sin dependencias externas."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

# --- Base de datos -----------------------------------------------------------
DB_PATH = os.environ.get("RB_DB_PATH", str(BASE_DIR / "report_builder.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

# --- Sesión ------------------------------------------------------------------
# Secreto para firmar la cookie de sesión. Cámbialo en producción.
SESSION_SECRET = os.environ.get("RB_SESSION_SECRET", "dev-inseguro-cambia-esto")
SESSION_COOKIE = "rb_session"
SESSION_MAX_AGE = int(os.environ.get("RB_SESSION_MAX_AGE", 60 * 60 * 24 * 14))  # 14 días
# En producción (HTTPS) pon RB_COOKIE_SECURE=1
COOKIE_SECURE = os.environ.get("RB_COOKIE_SECURE", "0") == "1"

# --- Proveedores de IA (keys server-side) ------------------------------------
AI_KEYS = {
    "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
    "openai": os.environ.get("OPENAI_API_KEY", ""),
    "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
}

# ¿Permitir registro abierto? En un servidor personal quizá quieras cerrarlo
# tras crear tu usuario (RB_ALLOW_REGISTER=0).
ALLOW_REGISTER = os.environ.get("RB_ALLOW_REGISTER", "1") == "1"
