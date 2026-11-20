from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ModelAsset, PrintJob
from app.schemas import PrintJobCreate, PrintJobOut, PrintJobUpdate
from app.services.files import absolute_from_storage, new_id

router = APIRouter(prefix="/print-jobs", tags=["print-jobs"])
settings = get_settings()


@router.post("", response_model=PrintJobOut)
def create_print_job(payload: PrintJobCreate, db: Session = Depends(get_db)):
    model = db.get(ModelAsset, payload.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    if model.check_status == "ERROR":
        raise HTTPException(status_code=400, detail="Cannot print model with ERROR check status")

    job = PrintJob(
        id=new_id(),
        model_id=model.id,
        material=payload.material,
        nozzle_mm=payload.nozzle_mm,
        slicer_profile=payload.slicer_profile,
        result_notes=payload.notes,
        status="DRAFT",
        export_path=model.file_path if model.format == "stl" else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[PrintJobOut])
def list_print_jobs(db: Session = Depends(get_db)):
    return db.query(PrintJob).order_by(PrintJob.created_at.desc()).all()


@router.patch("/{job_id}", response_model=PrintJobOut)
def update_print_job(job_id: str, payload: PrintJobUpdate, db: Session = Depends(get_db)):
    job = db.get(PrintJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Print job not found")

    if payload.status is not None:
        job.status = payload.status
    if payload.estimated_minutes is not None:
        job.estimated_minutes = payload.estimated_minutes
    if payload.result_notes is not None:
        job.result_notes = payload.result_notes

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/open-slicer")
def open_slicer(job_id: str, db: Session = Depends(get_db)):
    job = db.get(PrintJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Print job not found")

    model = db.get(ModelAsset, job.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model_path = absolute_from_storage(model.file_path, settings)
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model file missing")

    slicer = settings.bambu_studio_executable
    if not slicer or not Path(slicer).exists():
        return {
            "opened": False,
            "message": "Bambu Studio path not configured. Import the STL manually.",
            "model_path": str(model_path),
        }

    subprocess.Popen([slicer, str(model_path)], shell=False)
    job.status = "SLICER_OPENED"
    db.add(job)
    db.commit()
    return {"opened": True, "model_path": str(model_path), "slicer": slicer}
