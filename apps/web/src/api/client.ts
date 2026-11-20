import axios from "axios";
import type {
  CheckReport,
  GenerationTask,
  ModelAsset,
  PrintJob,
  Project,
} from "@/types";

const http = axios.create({
  baseURL: "",
  timeout: 120000,
});

export async function fetchHealth() {
  const { data } = await http.get("/api/health");
  return data as {
    status: string;
    blender_exists: boolean;
    blender_executable: string;
    ai_provider: string;
  };
}

export async function listProjects() {
  const { data } = await http.get<Project[]>("/api/v1/projects");
  return data;
}

export async function createProject(name: string, description?: string) {
  const { data } = await http.post<Project>("/api/v1/projects", { name, description });
  return data;
}

export async function listModels(projectId: string) {
  const { data } = await http.get<ModelAsset[]>(`/api/v1/projects/${projectId}/models`);
  return data;
}

export async function importModel(projectId: string, file: File, name?: string) {
  const form = new FormData();
  form.append("project_id", projectId);
  form.append("file", file);
  if (name) form.append("name", name);
  const { data } = await http.post<ModelAsset>("/api/v1/models/import", form);
  return data;
}

export async function processModel(
  modelId: string,
  payload: { target_height_mm: number; add_base: boolean; base_thickness_mm: number },
) {
  const { data } = await http.post<ModelAsset>(`/api/v1/models/${modelId}/process`, payload);
  return data;
}

export async function validateModel(modelId: string) {
  const { data } = await http.post<{ model: ModelAsset; report: CheckReport }>(
    `/api/v1/models/${modelId}/validate`,
    { max_bed_mm: 240 },
  );
  return data;
}

export async function exportModel(modelId: string) {
  const { data } = await http.post<{ model: ModelAsset; files: string[] }>(
    `/api/v1/models/${modelId}/export`,
    { confirmed: true, format: "stl" },
  );
  return data;
}

export async function createGeneration(projectId: string, prompt: string, provider?: string) {
  const { data } = await http.post<GenerationTask>("/api/v1/generation", {
    project_id: projectId,
    prompt,
    provider,
  });
  return data;
}

export async function getGeneration(taskId: string) {
  const { data } = await http.get<GenerationTask>(`/api/v1/generation/${taskId}`);
  return data;
}

export async function downloadGeneration(taskId: string) {
  const { data } = await http.post<{ task: GenerationTask; model: ModelAsset }>(
    `/api/v1/generation/${taskId}/download`,
  );
  return data;
}

export async function createPrintJob(modelId: string) {
  const { data } = await http.post<PrintJob>("/api/v1/print-jobs", {
    model_id: modelId,
    material: "PLA",
    nozzle_mm: 0.4,
  });
  return data;
}

export async function openSlicer(jobId: string) {
  const { data } = await http.post(`/api/v1/print-jobs/${jobId}/open-slicer`);
  return data as { opened: boolean; model_path: string; message?: string };
}

export function modelFileUrl(model: ModelAsset) {
  return `/storage/${model.file_path}`;
}
