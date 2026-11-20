export interface Project {
  id: string;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface ModelAsset {
  id: string;
  project_id: string;
  parent_model_id?: string | null;
  name: string;
  source_type: string;
  file_path: string;
  format: string;
  version: number;
  width_mm?: number | null;
  depth_mm?: number | null;
  height_mm?: number | null;
  check_status?: string | null;
  check_report_path?: string | null;
  created_at: string;
}

export interface GenerationTask {
  id: string;
  project_id: string;
  provider: string;
  provider_task_id?: string | null;
  prompt?: string | null;
  status: string;
  error_message?: string | null;
  output_path?: string | null;
  model_id?: string | null;
  created_at: string;
}

export interface PrintJob {
  id: string;
  model_id: string;
  printer_model: string;
  material: string;
  nozzle_mm: number;
  slicer_profile?: string | null;
  estimated_minutes?: number | null;
  status: string;
  result_notes?: string | null;
  export_path?: string | null;
  created_at: string;
}

export interface CheckReport {
  status: string;
  dimensions_mm?: { x: number; y: number; z: number };
  recommendations?: string[];
  checks?: Array<{ level: string; code: string; message: string }>;
}
