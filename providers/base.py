from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProviderTask:
    provider: str
    provider_task_id: str
    status: str
    progress: float = 0.0
    model_urls: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class Base3DProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def create_task(
        self,
        prompt: str | None = None,
        image_path: str | None = None,
    ) -> ProviderTask:
        raise NotImplementedError

    @abstractmethod
    async def get_task(self, task_id: str) -> ProviderTask:
        raise NotImplementedError

    @abstractmethod
    async def download_model(self, task_id: str, output_dir: Path) -> Path:
        raise NotImplementedError
