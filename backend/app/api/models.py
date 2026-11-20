from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ModelAsset, Project
from app.schemas import ExportRequest, ModelOut, ModelProcessRequest, ValidateRequest
from app.services.blender import BlenderRunner
from app.services.files import (
    absolute_from_storage,
    new_id,
    relative_to_storage,
    safe_stem,
    save_upload,
)

router = APIRouter(tags=["models"])
settings = get_settings()


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_model(db: Session, model_id: str) -> ModelAsset:
    model = db.get(ModelAsset, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/models/import", response_model=ModelOut)
async def import_model(
    project_id: str = Form(...),
    name: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _get_project(db, project_id)
    try:
        saved = await save_upload(file, settings, "source", project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    model = ModelAsset(
        id=new_id(),
        project_id=project_id,
        parent_model_id=None,
        name=name or Path(file.filename or saved.name).stem,
        source_type="import",
        file_path=relative_to_storage(saved, settings),
        format=saved.suffix.lstrip(".").lower(),
        version=1,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.get("/projects/{project_id}/models", response_model=list[ModelOut])
def list_project_models(project_id: str, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    return (
        db.query(ModelAsset)
        .filter(ModelAsset.project_id == project_id)
        .order_by(ModelAsset.created_at.desc())
        .all()
    )


@router.get("/models/{model_id}", response_model=ModelOut)
def get_model(model_id: str, db: Session = Depends(get_db)):
    return _get_model(db, model_id)


@router.get("/models/{model_id}/file")
def download_model_file(model_id: str, db: Session = Depends(get_db)):
    model = _get_model(db, model_id)
    path = absolute_from_storage(model.file_path, settings)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(path, filename=path.name)


@router.post("/models/{model_id}/process", response_model=ModelOut)
def process_model(
    model_id: str,
    payload: ModelProcessRequest,
    db: Session = Depends(get_db),
):
    model = _get_model(db, model_id)
    source = absolute_from_storage(model.file_path, settings)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Source file missing")

    runner = BlenderRunner(settings)
    processed_dir = settings.storage_root / "processed" / model.project_id
    processed_dir.mkdir(parents=True, exist_ok=True)
    blend_path = processed_dir / f"{safe_stem(model.name)}_{model.id[:8]}.blend"

    import_result = runner.run_script(
        "import_model.py",
        {"input": str(source), "output": str(blend_path)},
    )
    if not import_result.success:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Blender import failed",
                "stderr": import_result.stderr,
                "stdout": import_result.stdout,
            },
        )

    normalize_result = runner.run_script(
        "normalize_model.py",
        {
            "blend": str(blend_path),
            "output": str(blend_path),
            "target_height_mm": payload.target_height_mm,
            "add_base": payload.add_base,
            "base_thickness_mm": payload.base_thickness_mm,
        },
    )
    if not normalize_result.success:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Blender normalize failed",
                "stderr": normalize_result.stderr,
                "stdout": normalize_result.stdout,
            },
        )

    dims = {}
    if isinstance(normalize_result.data, dict):
        dims = normalize_result.data.get("dimensions_mm") or {}

    processed = ModelAsset(
        id=new_id(),
        project_id=model.project_id,
        parent_model_id=model.id,
        name=f"{model.name}_processed",
        source_type="processed",
        file_path=relative_to_storage(blend_path, settings),
        format="blend",
        version=model.version + 1,
        width_mm=dims.get("width_mm"),
        depth_mm=dims.get("depth_mm"),
        height_mm=dims.get("height_mm"),
    )
    db.add(processed)
    db.commit()
    db.refresh(processed)
    return processed


@router.post("/models/{model_id}/validate")
def validate_model(
    model_id: str,
    payload: ValidateRequest,
    db: Session = Depends(get_db),
):
    model = _get_model(db, model_id)
    source = absolute_from_storage(model.file_path, settings)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Source file missing")

    runner = BlenderRunner(settings)
    work_blend = source
    if source.suffix.lower() != ".blend":
        processed_dir = settings.storage_root / "processed" / model.project_id
        processed_dir.mkdir(parents=True, exist_ok=True)
        work_blend = processed_dir / f"{safe_stem(model.name)}_{model.id[:8]}_validate.blend"
        imported = runner.run_script(
            "import_model.py",
            {"input": str(source), "output": str(work_blend)},
        )
        if not imported.success:
            raise HTTPException(status_code=500, detail="Failed to import model for validation")

    report_path = (
        settings.storage_root
        / "processed"
        / model.project_id
        / f"{safe_stem(model.name)}_{model.id[:8]}_report.json"
    )
    result = runner.run_script(
        "validate_print.py",
        {
            "blend": str(work_blend),
            "report": str(report_path),
            "max_bed_mm": payload.max_bed_mm,
        },
    )
    if not result.success or not isinstance(result.data, dict):
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Validation failed",
                "stderr": result.stderr,
                "stdout": result.stdout,
            },
        )

    model.check_status = result.data.get("status")
    model.check_report_path = relative_to_storage(report_path, settings)
    dims = result.data.get("dimensions_mm") or {}
    model.width_mm = dims.get("x")
    model.depth_mm = dims.get("y")
    model.height_mm = dims.get("z")
    db.add(model)
    db.commit()
    db.refresh(model)

    return {"model": ModelOut.model_validate(model), "report": result.data}


@router.post("/models/{model_id}/export")
def export_model(
    model_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
):
    model = _get_model(db, model_id)
    if not payload.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Export requires confirmed=true after human review",
        )
    if model.check_status == "ERROR":
        raise HTTPException(
            status_code=400,
            detail="Model check status is ERROR; fix issues before export",
        )

    source = absolute_from_storage(model.file_path, settings)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Source file missing")

    runner = BlenderRunner(settings)
    work_blend = source
    if source.suffix.lower() != ".blend":
        processed_dir = settings.storage_root / "processed" / model.project_id
        processed_dir.mkdir(parents=True, exist_ok=True)
        work_blend = processed_dir / f"{safe_stem(model.name)}_{model.id[:8]}_export.blend"
        imported = runner.run_script(
            "import_model.py",
            {"input": str(source), "output": str(work_blend)},
        )
        if not imported.success:
            raise HTTPException(status_code=500, detail="Failed to import model for export")

    export_dir = settings.storage_root / "exports" / model.project_id
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"{safe_stem(model.name)}_{model.id[:8]}.stl"

    result = runner.run_script(
        "export_print.py",
        {"blend": str(work_blend), "output": str(export_path), "per_object": False},
    )
    if not result.success:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Export failed",
                "stderr": result.stderr,
                "stdout": result.stdout,
            },
        )

    exported = ModelAsset(
        id=new_id(),
        project_id=model.project_id,
        parent_model_id=model.id,
        name=f"{model.name}_stl",
        source_type="export",
        file_path=relative_to_storage(export_path, settings),
        format="stl",
        version=model.version + 1,
        width_mm=model.width_mm,
        depth_mm=model.depth_mm,
        height_mm=model.height_mm,
        check_status=model.check_status,
        check_report_path=model.check_report_path,
    )
    db.add(exported)
    db.commit()
    db.refresh(exported)
    return {
        "model": ModelOut.model_validate(exported),
        "files": result.data.get("files") if isinstance(result.data, dict) else [str(export_path)],
    }


@router.get("/models/{model_id}/files")
def list_model_files(model_id: str, db: Session = Depends(get_db)):
    model = _get_model(db, model_id)
    related = (
        db.query(ModelAsset)
        .filter(
            (ModelAsset.id == model_id)
            | (ModelAsset.parent_model_id == model_id)
            | (ModelAsset.parent_model_id == model.parent_model_id)
        )
        .order_by(ModelAsset.created_at.asc())
        .all()
    )
    files = []
    for item in related:
        path = absolute_from_storage(item.file_path, settings)
        files.append(
            {
                "id": item.id,
                "name": item.name,
                "source_type": item.source_type,
                "format": item.format,
                "path": item.file_path,
                "exists": path.exists(),
                "check_status": item.check_status,
            }
        )

    report = None
    if model.check_report_path:
        report_file = absolute_from_storage(model.check_report_path, settings)
        if report_file.exists():
            report = json.loads(report_file.read_text(encoding="utf-8"))

    return {"model_id": model_id, "files": files, "report": report}
