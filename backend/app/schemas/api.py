from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelOut(BaseModel):
    id: str
    project_id: str
    parent_model_id: str | None
    name: str
    source_type: str
    file_path: str
    format: str
    version: int
    width_mm: float | None
    depth_mm: float | None
    height_mm: float | None
    check_status: str | None
    check_report_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelProcessRequest(BaseModel):
    target_height_mm: float = 100.0
    add_base: bool = False
    base_thickness_mm: float = 2.0


class ValidateRequest(BaseModel):
    max_bed_mm: float = 240.0
    min_wall_hint_mm: float = 1.2


class ExportRequest(BaseModel):
    confirmed: bool = False
    format: str = "stl"


class GenerationCreate(BaseModel):
    project_id: str
    prompt: str | None = None
    provider: str | None = None
    mode: str = "text-to-3d"


class GenerationOut(BaseModel):
    id: str
    project_id: str
    provider: str
    provider_task_id: str | None
    prompt: str | None
    status: str
    error_message: str | None
    output_path: str | None
    model_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PrintJobCreate(BaseModel):
    model_id: str
    material: str = "PLA"
    nozzle_mm: float = 0.4
    slicer_profile: str | None = None
    notes: str | None = None


class PrintJobUpdate(BaseModel):
    status: str | None = None
    estimated_minutes: int | None = None
    result_notes: str | None = None


class PrintJobOut(BaseModel):
    id: str
    model_id: str
    printer_model: str
    material: str
    nozzle_mm: float
    slicer_profile: str | None
    estimated_minutes: int | None
    status: str
    result_notes: str | None
    export_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
