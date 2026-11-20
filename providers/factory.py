from __future__ import annotations

from app.config import Settings
from providers.base import Base3DProvider
from providers.meshy import MeshyProvider
from providers.tripo import TripoProvider


def get_provider(settings: Settings, name: str | None = None) -> Base3DProvider:
    provider_name = (name or settings.ai_provider or "meshy").lower()
    if provider_name == "meshy":
        return MeshyProvider(api_key=settings.meshy_api_key, base_url=settings.meshy_base_url)
    if provider_name == "tripo":
        return TripoProvider(api_key=settings.tripo_api_key, base_url=settings.tripo_base_url)
    raise ValueError(f"Unsupported AI provider: {provider_name}")
