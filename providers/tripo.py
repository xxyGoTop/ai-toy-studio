from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from providers.base import Base3DProvider, ProviderTask

STATUS_MAP = {
    "queued": "PENDING",
    "running": "IN_PROGRESS",
    "success": "SUCCEEDED",
    "failed": "FAILED",
    "cancelled": "CANCELED",
    "canceled": "CANCELED",
}


class TripoProvider(Base3DProvider):
    name = "tripo"

    def __init__(self, api_key: str, base_url: str = "https://api.tripo3d.ai"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_task(
        self,
        prompt: str | None = None,
        image_path: str | None = None,
    ) -> ProviderTask:
        if not self.api_key or self.api_key.strip() in {"your_api_key", "your_tripo_api_key"}:
            raise RuntimeError(
                "还没有可用的 Tripo API Key。请在项目根目录 .env 把 TRIPO_API_KEY 换成 Tripo 控制台的真实密钥，保存后重启后端。"
            )

        if image_path:
            raise NotImplementedError(
                "Tripo image-to-3d upload needs official multipart endpoint; configure after API review"
            )
        if not prompt:
            raise ValueError("prompt is required for text-to-3d")

        payload = {
            "type": "text_to_model",
            "prompt": prompt,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/v2/openapi/task",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            task_id = (data.get("data") or {}).get("task_id") or data.get("task_id")
            if not task_id:
                raise RuntimeError(f"Unexpected Tripo response: {data}")
            return ProviderTask(
                provider=self.name,
                provider_task_id=str(task_id),
                status="SUBMITTED",
                raw=data,
            )

    async def get_task(self, task_id: str) -> ProviderTask:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self.base_url}/v2/openapi/task/{task_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            data = payload.get("data") or payload
            status = STATUS_MAP.get(str(data.get("status", "")).lower(), "IN_PROGRESS")
            output = data.get("output") or {}
            model_urls = {}
            for key in ("model", "pbr_model", "base_model", "gltf", "glb"):
                if output.get(key):
                    model_urls[key] = output[key]
            return ProviderTask(
                provider=self.name,
                provider_task_id=task_id,
                status=status,
                progress=float(data.get("progress") or 0),
                model_urls=model_urls,
                raw=payload,
                error_message=data.get("error_msg") or data.get("message"),
            )

    async def download_model(self, task_id: str, output_dir: Path) -> Path:
        task = await self.get_task(task_id)
        if task.status != "SUCCEEDED":
            raise RuntimeError(f"Task not ready: {task.status}")

        url = (
            task.model_urls.get("model")
            or task.model_urls.get("glb")
            or task.model_urls.get("gltf")
            or task.model_urls.get("pbr_model")
        )
        if not url:
            raise RuntimeError("No downloadable model URL in Tripo response")

        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"tripo_{task_id}.glb"
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
        return target
