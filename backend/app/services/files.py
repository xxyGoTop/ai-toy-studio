from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import Settings


ALLOWED_EXTENSIONS = {".stl", ".obj", ".glb", ".gltf", ".3mf", ".blend", ".png", ".jpg", ".jpeg", ".webp"}
COMPANION_EXTENSIONS = {".bin", ".png", ".jpg", ".jpeg", ".webp"}


def new_id() -> str:
    return str(uuid.uuid4())


def safe_stem(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.strip())
    return cleaned[:80] or "model"


async def save_upload(
    upload: UploadFile,
    settings: Settings,
    category: str,
    project_id: str,
) -> Path:
    suffix = Path(upload.filename or "model.bin").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    folder = settings.storage_root / category / project_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{safe_stem(Path(upload.filename or 'model').stem)}_{new_id()[:8]}{suffix}"

    with target.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)

    return target


def copy_file(src: Path, settings: Settings, category: str, project_id: str, name: str) -> Path:
    folder = settings.storage_root / category / project_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    shutil.copy2(src, target)
    return target


def relative_to_storage(path: Path, settings: Settings) -> str:
    try:
        return path.resolve().relative_to(settings.storage_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def absolute_from_storage(relative_path: str, settings: Settings) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return (settings.storage_root / path).resolve()


def relative_upload_path(raw: str) -> Path:
    text = (raw or "").replace("\\", "/").split("?", 1)[0].split("#", 1)[0]
    parts = [part for part in text.split("/") if part not in {"", ".", ".."}]
    if not parts:
        raise ValueError("文件名为空")
    return Path(*parts)


def remove_stored_file(relative_path: str, settings: Settings) -> None:
    path = absolute_from_storage(relative_path, settings)
    root = settings.storage_root.resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return
    parent = path.parent
    # 一次导入的 GLTF 和 .bin / 贴图放在独立目录里，删除时一起清掉。
    if len(Path(relative_path).parts) >= 4 and parent.is_dir() and parent != root:
        shutil.rmtree(parent, ignore_errors=True)
        return
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
