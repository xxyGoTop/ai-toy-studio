from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import GenerationTask, ModelAsset, Project
from app.schemas import GenerationCreate, GenerationOut, ModelOut
from app.services.files import new_id, relative_to_storage, save_upload
from providers.factory import get_provider

router = APIRouter(prefix="/generation", tags=["generation"])
settings = get_settings()


@router.post("", response_model=GenerationOut)
async def create_generation(
    payload: GenerationCreate,
    db: Session = Depends(get_db),
):
    project = db.get(Project, payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not payload.prompt:
        raise HTTPException(status_code=400, detail="prompt is required for text generation")

    provider_name = payload.provider or settings.ai_provider
    task = GenerationTask(
        id=new_id(),
        project_id=payload.project_id,
        provider=provider_name,
        prompt=payload.prompt,
        status="PENDING",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        provider = get_provider(settings, provider_name)
        provider_task = await provider.create_task(prompt=payload.prompt)
        task.provider_task_id = provider_task.provider_task_id
        task.status = provider_task.status or "SUBMITTED"
    except Exception as exc:  # noqa: BLE001
        task.status = "FAILED"
        task.error_message = str(exc)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/image-to-3d", response_model=GenerationOut)
async def create_image_generation(
    project_id: str = Form(...),
    prompt: str | None = Form(None),
    provider: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        image_path = await save_upload(file, settings, "source", project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    provider_name = provider or settings.ai_provider
    task = GenerationTask(
        id=new_id(),
        project_id=project_id,
        provider=provider_name,
        prompt=prompt,
        image_path=relative_to_storage(image_path, settings),
        status="PENDING",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        provider_client = get_provider(settings, provider_name)
        provider_task = await provider_client.create_task(
            prompt=prompt,
            image_path=str(image_path),
        )
        task.provider_task_id = provider_task.provider_task_id
        task.status = provider_task.status or "SUBMITTED"
    except Exception as exc:  # noqa: BLE001
        task.status = "FAILED"
        task.error_message = str(exc)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=GenerationOut)
async def get_generation(task_id: str, db: Session = Depends(get_db)):
    task = db.get(GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Generation task not found")

    if task.provider_task_id and task.status not in {"SUCCEEDED", "FAILED", "CANCELED"}:
        try:
            provider = get_provider(settings, task.provider)
            remote = await provider.get_task(task.provider_task_id)
            task.status = remote.status
            task.error_message = remote.error_message
            db.add(task)
            db.commit()
            db.refresh(task)
        except Exception as exc:  # noqa: BLE001
            task.error_message = str(exc)
            db.add(task)
            db.commit()
            db.refresh(task)

    return task


@router.post("/{task_id}/download")
async def download_generation(task_id: str, db: Session = Depends(get_db)):
    task = db.get(GenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Generation task not found")
    if not task.provider_task_id:
        raise HTTPException(status_code=400, detail="Provider task id missing")

    provider = get_provider(settings, task.provider)
    remote = await provider.get_task(task.provider_task_id)
    if remote.status != "SUCCEEDED":
        task.status = remote.status
        task.error_message = remote.error_message
        db.add(task)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Task not ready: {remote.status}")

    output_dir = settings.storage_root / "generated" / task.project_id
    try:
        downloaded = await provider.download_model(task.provider_task_id, output_dir)
    except Exception as exc:  # noqa: BLE001
        task.status = "FAILED"
        task.error_message = str(exc)
        db.add(task)
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    model = ModelAsset(
        id=new_id(),
        project_id=task.project_id,
        parent_model_id=None,
        name=f"ai_{task.provider}_{task.id[:8]}",
        source_type="ai_generated",
        file_path=relative_to_storage(downloaded, settings),
        format=downloaded.suffix.lstrip(".").lower(),
        version=1,
    )
    db.add(model)
    task.status = "SUCCEEDED"
    task.output_path = model.file_path
    task.model_id = model.id
    db.add(task)
    db.commit()
    db.refresh(task)
    db.refresh(model)

    return {
        "task": GenerationOut.model_validate(task),
        "model": ModelOut.model_validate(model),
    }
