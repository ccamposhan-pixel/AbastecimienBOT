from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..config.settings import Settings
from .providers import LLMClient, LLMConfigurationError, client_from_settings


@dataclass(frozen=True)
class PanelMessage:
    provider: str
    model: str
    role: str
    content: str


def run_panel_discussion(
    *,
    settings: Settings,
    providers: Iterable[str],
    question: str,
    primary_answer: str,
    max_tokens: int = 500,
) -> list[PanelMessage]:
    """Pide a distintos modelos que revisen una respuesta y generen discusión breve.

    Si una API key no está configurada, omite el proveedor.
    """
    panel: list[PanelMessage] = []
    system = (
        "Eres un revisor ejecutivo de abastecimiento hospitalario. "
        "Debes: (1) detectar supuestos, (2) señalar riesgos/omisiones, "
        "(3) proponer mejoras accionables. Responde en español."
    )
    user = (
        "Consulta del usuario:\n"
        f"{question}\n\n"
        "Respuesta propuesta por el equipo interno:\n"
        f"{primary_answer}\n\n"
        "Entrega una revisión en 6-10 viñetas y termina con un veredicto corto: "
        "APROBADO / APROBADO_CON_OBSERVACIONES / RECHAZADO."
    )
    for provider in providers:
        try:
            client = client_from_settings(settings, provider)
        except LLMConfigurationError:
            continue
        result = _generate_review(settings, client, system=system, user=user, max_tokens=max_tokens)
        panel.append(
            PanelMessage(
                provider=result["provider"],
                model=result["model"],
                role="reviewer",
                content=result["text"],
            )
        )
    return panel


def _generate_review(
    settings: Settings,
    client: LLMClient,
    *,
    system: str,
    user: str,
    max_tokens: int,
) -> dict[str, Any]:
    if getattr(client, "provider", "") == "anthropic":
        model = settings.anthropic_model
    else:
        model = settings.gemini_model
    result = client.generate_text(model=model, system=system, user=user, temperature=0.2, max_tokens=max_tokens)
    return {"provider": result.provider, "model": result.model, "text": result.text, "raw": result.raw}

