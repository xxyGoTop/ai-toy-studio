from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from providers.base import Base3DProvider, ProviderTask

STATUS_MAP = {
    "PENDING": "PENDING",
    "IN_PROGRESS": "IN_PROGRESS",
    "SUCCEEDED": "SUCCEEDED",
    "FAILED": "FAILED",
    "CANCELED": "CANCELED",
}


class MeshyProvider(Base3DProvider):
    name = "meshy"

    def __init__(self, api_key: str, base_url: str = "https://api.meshy.ai"):
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
        if not self.api_key:
            raise RuntimeError("MESHY_API_KEY is not configured")

        async with httpx.AsyncClient(timeout=60.0) as client:
            if image_path:
                # Image-to-3D: upload image URL/path handling left to caller for production.
                # First version expects a public URL or local file prepared by backend.
                files = {"image": Path(image_path).open("rb")}
                try:
                    response = await client.post(
                        f"{self.base_url}/openapi/v1/image-to-3d",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data={"enable_pbr": "false"},
                        files=files,
                    )
                finally:
                    files["image"].close()
            else:
                if not prompt:
                    raise ValueError("prompt is required for text-to-3d")
                payload = {
                    "mode": "preview",
                    "prompt": prompt,
                    "art_style": "sculpture",
                    "should_remesh": True,
                }
                response = await client.post(
                    f"{self.base_url}/openapi/v2/text-to-3d",
                    headers=self._headers(),
                    json=payload,
                )

            response.raise_for_status()
            data = response.json()
            task_id = data.get("result") or data.get("id")
            if not task_id:
                raise RuntimeError(f"Unexpected Meshy response: {data}")
            return ProviderTask(
                provider=self.name,
                provider_task_id=str(task_id),
                status="SUBMITTED",
                raw=data,
            )

    async def get_task(self, task_id: str) -> ProviderTask:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Try text-to-3d first, then image-to-3d.
            for path in (
                f"/openapi/v2/text-to-3d/{task_id}",
                f"/openapi/v1/image-to-3d/{task_id}",
            ):
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                )
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                status = STATUS_MAP.get(str(data.get("status", "")).upper(), "IN_PROGRESS")
                model_urls = data.get("model_urls") or {}
                return ProviderTask(
                    provider=self.name,
                    provider_task_id=task_id,
                    status=status,
                    progress=float(data.get("progress") or 0),
                    model_urls=model_urls,
                    raw=data,
                    error_message=data.get("task_error", {}).get("message")
                    if isinstance(data.get("task_error"), dict)
                    else data.get("error"),
                )
            raise RuntimeError(f"Meshy task not found: {task_id}")

    async def download_model(self, task_id: str, output_dir: Path) -> Path:
        task = await self.get_task(task_id)
        if task.status != "SUCCEEDED":
            raise RuntimeError(f"Task not ready: {task.status}")

        url = task.model_urls.get("glb") or task.model_urls.get("obj") or task.model_urls.get("fbx")
        if not url:
            raise RuntimeError("No downloadable model URL in Meshy response")

        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".glb" if "glb" in url or task.model_urls.get("glb") else ".obj"
        target = output_dir / f"meshy_{task_id}{suffix}"

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
        return target
