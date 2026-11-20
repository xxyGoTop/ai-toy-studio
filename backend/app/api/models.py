from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ModelAsset, PrintJob, Project
from app.schemas import ExportRequest, ModelOut, ModelProcessRequest, ValidateRequest
from app.services.bambu_color import build_colored_3mf, open_studio
from app.services.blender import BlenderRunner
from app.services.files import (
    ALLOWED_EXTENSIONS,
    COMPANION_EXTENSIONS,
    absolute_from_storage,
    new_id,
    relative_to_storage,
    relative_upload_path,
    remove_stored_file,
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


def _external_gltf_uris(payload: dict) -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    for group in ("buffers", "images"):
        for item in payload.get(group) or []:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri")
            if not isinstance(uri, str) or uri.startswith("data:") or "://" in uri:
                continue
            found.append((uri.split("?", 1)[0].split("#", 1)[0], item))
    return found


def _link_gltf_dependencies(gltf_path: Path, folder: Path) -> None:
    try:
        payload = json.loads(gltf_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError("GLTF 文件不是有效的 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("GLTF 文件不是有效的 JSON")

    by_name: dict[str, Path] = {}
    for child in folder.rglob("*"):
        if child.is_file() and child != gltf_path:
            by_name.setdefault(child.name, child)

    missing: list[str] = []
    changed = False
    folder_resolved = folder.resolve()
    for clean, item in _external_gltf_uris(payload):
        try:
            expected = (folder / relative_upload_path(clean)).resolve()
            expected.relative_to(folder_resolved)
        except ValueError:
            missing.append(clean)
            continue
        if expected.is_file():
            continue
        match = by_name.get(Path(clean).name)
        if match is None:
            missing.append(clean)
            continue
        item["uri"] = match.resolve().relative_to(folder_resolved).as_posix()
        changed = True

    if missing:
        names = "、".join(missing)
        raise ValueError(f"这个 GLTF 还依赖外部文件：{names}。请和 .gltf 一起选中后再上传。")
    if changed:
        gltf_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


async def _write_upload(upload: UploadFile, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


@router.post("/models/import", response_model=ModelOut)
async def import_model(
    project_id: str = Form(...),
    name: str | None = Form(None),
    file: UploadFile = File(...),
    main_path: str | None = Form(None),
    companions: list[UploadFile] | None = File(None),
    companion_paths: list[str] | None = Form(None),
    db: Session = Depends(get_db),
):
    _get_project(db, project_id)
    original_name = file.filename or "model"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS or suffix == ".bin":
        raise HTTPException(status_code=400, detail=f"不支持的模型格式：{suffix or '未知'}")

    model_id = new_id()
    folder = settings.storage_root / "source" / project_id / model_id
    folder.mkdir(parents=True, exist_ok=True)
    saved = folder / f"{safe_stem(Path(original_name).stem)}{suffix}"
    try:
        await _write_upload(file, saved)
        extras = companions or []
        paths = companion_paths or []
        main_relative = relative_upload_path(main_path or original_name)
        main_dir = main_relative.parts[:-1]
        for index, extra in enumerate(extras):
            extra_name = paths[index] if index < len(paths) else (extra.filename or "")
            extra_relative = relative_upload_path(extra_name or extra.filename or "extra.bin")
            if extra_relative.suffix.lower() not in COMPANION_EXTENSIONS:
                continue
            if main_dir and extra_relative.parts[: len(main_dir)] == main_dir:
                extra_relative = Path(*extra_relative.parts[len(main_dir) :])
            else:
                extra_relative = Path(extra_relative.name)
            if not extra_relative.parts:
                continue
            await _write_upload(extra, folder / extra_relative)
        if suffix == ".gltf":
            _link_gltf_dependencies(saved, folder)
    except ValueError as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    model = ModelAsset(
        id=model_id,
        project_id=project_id,
        parent_model_id=None,
        name=name or Path(original_name).stem,
        source_type="import",
        file_path=relative_to_storage(saved, settings),
        format=suffix.lstrip(".").lower(),
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


@router.delete("/models/{model_id}")
def delete_model(model_id: str, db: Session = Depends(get_db)):
    model = _get_model(db, model_id)
    file_path = model.file_path
    db.query(PrintJob).filter(PrintJob.model_id == model_id).delete()
    db.delete(model)
    db.commit()

    still_used = db.query(ModelAsset).filter(ModelAsset.file_path == file_path).count()
    if still_used == 0:
        remove_stored_file(file_path, settings)
    return {"deleted": model_id}


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
    preview_path = blend_path
    preview_format = "blend"
    if isinstance(normalize_result.data, dict):
        dims = normalize_result.data.get("dimensions_mm") or {}
        preview = normalize_result.data.get("preview")
        if preview and Path(preview).exists():
            preview_path = Path(preview)
            preview_format = "glb"

    processed = ModelAsset(
        id=new_id(),
        project_id=model.project_id,
        parent_model_id=model.id,
        name=f"{model.name}_processed",
        source_type="processed",
        file_path=relative_to_storage(preview_path, settings),
        format=preview_format,
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


@router.post("/models/{model_id}/split")
def split_model(model_id: str, db: Session = Depends(get_db)):
    model = _get_model(db, model_id)
    source = absolute_from_storage(model.file_path, settings)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Source file missing")
    if source.suffix.lower() not in {".glb", ".gltf", ".stl", ".obj", ".blend"}:
        raise HTTPException(status_code=400, detail="这个格式还不能按颜色拆分")

    split_dir = settings.storage_root / "processed" / model.project_id
    split_dir.mkdir(parents=True, exist_ok=True)
    output = split_dir / f"{safe_stem(model.name)}_{model.id[:8]}_split.glb"
    result = BlenderRunner(settings).run_script(
        "split_by_color.py",
        {"input": str(source), "output": str(output)},
    )
    if not result.success or not isinstance(result.data, dict):
        detail = "拆分失败"
        if isinstance(result.data, dict) and result.data.get("error"):
            detail = str(result.data["error"])
        elif result.stderr:
            detail = result.stderr[-500:]
        raise HTTPException(status_code=500, detail=detail)

    created = ModelAsset(
        id=new_id(),
        project_id=model.project_id,
        parent_model_id=model.id,
        name=f"{model.name}_拆分",
        source_type="split",
        file_path=relative_to_storage(output, settings),
        format="glb",
        version=model.version + 1,
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    return {
        "model": ModelOut.model_validate(created),
        "mode": result.data.get("mode"),
        "parts": result.data.get("parts") or [],
    }


def _print_source(db: Session, model: ModelAsset) -> ModelAsset:
    current = model
    seen: set[str] = set()
    while current.source_type == "split" and current.parent_model_id and current.id not in seen:
        seen.add(current.id)
        parent = db.get(ModelAsset, current.parent_model_id)
        if parent is None:
            break
        current = parent
    if current.source_type != "split":
        return current

    base = current.name
    while base.endswith("_拆分"):
        base = base[: -len("_拆分")]
    imported = (
        db.query(ModelAsset)
        .filter(ModelAsset.project_id == current.project_id, ModelAsset.source_type == "import", ModelAsset.name == base)
        .order_by(ModelAsset.created_at.asc())
        .all()
    )
    for item in imported:
        if item.format in {"glb", "gltf", "obj", "stl", "blend"}:
            return item
    return current


@router.post("/models/{model_id}/open-colored")
def open_colored_slicer(model_id: str, db: Session = Depends(get_db)):
    model = _print_source(db, _get_model(db, model_id))
    if model.check_status == "ERROR":
        raise HTTPException(status_code=400, detail="网格检查未通过，先处理后再打开切片")

    source = absolute_from_storage(model.file_path, settings)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Source file missing")
    suffix = source.suffix.lower()
    if suffix not in {".glb", ".gltf", ".stl", ".obj", ".blend"}:
        raise HTTPException(status_code=400, detail="这个格式还不能生成彩色切片项目")

    export_dir = settings.storage_root / "exports" / model.project_id
    dest = export_dir / f"{safe_stem(model.name)}_{model.id[:8]}_color.3mf"
    unit_scale = 1000.0 if suffix in {".glb", ".gltf"} else 1.0
    try:
        built = build_colored_3mf(settings, source, dest, unit_scale)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    relative = relative_to_storage(dest, settings)
    job = PrintJob(
        id=new_id(),
        model_id=model.id,
        material="PLA",
        nozzle_mm=0.4,
        slicer_profile="0.20mm Standard @BBL A1",
        status="SLICER_OPENED",
        export_path=relative,
        result_notes="、".join(f"{part['slot']}:{part['color']}" for part in built["parts"]),
    )
    db.add(job)
    db.commit()
    open_studio(settings, dest)
    return {
        "opened": True,
        "path": str(dest),
        "slots": built["parts"],
        "source_colors": built["source_colors"],
        "assembled_from": model.name,
    }


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
