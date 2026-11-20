from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import GenerationTask, ModelAsset, PrintJob, Project
from app.schemas import ProjectCreate, ProjectOut
from app.services.files import absolute_from_storage, new_id, remove_stored_file

router = APIRouter(prefix="/projects", tags=["projects"])
settings = get_settings()


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(id=new_id(), name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _unlink_storage(relative_path: str | None) -> None:
    if not relative_path:
        return
    path = absolute_from_storage(relative_path, settings)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    models = db.query(ModelAsset).filter(ModelAsset.project_id == project_id).all()
    model_ids = [model.id for model in models]
    model_files = [model.file_path for model in models if model.file_path]
    extra_files = [model.check_report_path for model in models if model.check_report_path]

    tasks = db.query(GenerationTask).filter(GenerationTask.project_id == project_id).all()
    for task in tasks:
        extra_files.append(task.image_path)
        extra_files.append(task.output_path)

    if model_ids:
        db.query(PrintJob).filter(PrintJob.model_id.in_(model_ids)).delete(synchronize_session=False)
        db.query(ModelAsset).filter(ModelAsset.id.in_(model_ids)).delete(synchronize_session=False)
    db.query(GenerationTask).filter(GenerationTask.project_id == project_id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()

    for relative in model_files:
        still_used = db.query(ModelAsset).filter(ModelAsset.file_path == relative).count()
        if still_used == 0:
            remove_stored_file(relative, settings)
    for relative in extra_files:
        _unlink_storage(relative)
    return {"deleted": project_id}
