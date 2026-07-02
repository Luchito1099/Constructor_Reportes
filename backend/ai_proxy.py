"""Proxy de IA. El navegador llama a /api/ai; la API key vive SOLO aquí.

Soporta Anthropic, OpenAI y DeepSeek. El cliente manda `provider`, `system` y
`messages` ([{role, content}]); devolvemos `{text}` con la respuesta.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import current_user, require_admin
from config import AI_KEYS
from db import User

router = APIRouter(prefix="/api/ai", tags=["ai"])

PROVIDERS = {
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "model": "claude-sonnet-5",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
    },
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
    },
}


class Msg(BaseModel):
    role: str
    content: str


class AIRequest(BaseModel):
    provider: str = "anthropic"
    model: str | None = None
    system: str = ""
    messages: list[Msg] = []
    max_tokens: int = 1600


class AIResponse(BaseModel):
    text: str


@router.get("/providers")
def providers(_: User = Depends(current_user)) -> dict:
    """Qué proveedores tienen key configurada (sin revelar la key)."""
    return {p: bool(AI_KEYS.get(p)) for p in PROVIDERS}


@router.post("", response_model=AIResponse)
async def ask(req: AIRequest, _: User = Depends(require_admin)) -> AIResponse:
    prov = PROVIDERS.get(req.provider)
    if not prov:
        raise HTTPException(400, f"Proveedor desconocido: {req.provider}")
    key = AI_KEYS.get(req.provider, "")
    if not key:
        raise HTTPException(
            400,
            f"No hay API key configurada para {req.provider} en el servidor "
            f"(define la variable de entorno correspondiente).",
        )
    model = req.model or prov["model"]
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            if req.provider == "anthropic":
                r = await client.post(
                    prov["url"],
                    headers={
                        "content-type": "application/json",
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": model,
                        "max_tokens": req.max_tokens,
                        "system": req.system,
                        "messages": msgs,
                    },
                )
                data = r.json()
                if r.status_code >= 400:
                    raise HTTPException(r.status_code, _err(data))
                text = "".join(
                    c.get("text", "") for c in data.get("content", [])
                )
            else:  # openai / deepseek (formato compatible)
                full = ([{"role": "system", "content": req.system}] if req.system else []) + msgs
                r = await client.post(
                    prov["url"],
                    headers={
                        "content-type": "application/json",
                        "authorization": f"Bearer {key}",
                    },
                    json={"model": model, "messages": full, "temperature": 0.2},
                )
                data = r.json()
                if r.status_code >= 400:
                    raise HTTPException(r.status_code, _err(data))
                text = data["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Error de red con el proveedor: {exc}") from exc

    return AIResponse(text=text)


def _err(data: dict) -> str:
    err = data.get("error")
    if isinstance(err, dict):
        return err.get("message", str(err))
    return str(err or data)
