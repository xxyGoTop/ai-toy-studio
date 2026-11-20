import { defineStore } from "pinia";
import { ref } from "vue";
import type { CheckReport, GenerationTask, ModelAsset, Project } from "@/types";
import * as api from "@/api/client";

export const useStudioStore = defineStore("studio", () => {
  const health = ref<{ blender_exists: boolean; ai_provider: string } | null>(null);
  const projects = ref<Project[]>([]);
  const models = ref<ModelAsset[]>([]);
  const currentProjectId = ref<string | null>(null);
  const currentModel = ref<ModelAsset | null>(null);
  const report = ref<CheckReport | null>(null);
  const generation = ref<GenerationTask | null>(null);
  const statusText = ref("就绪");
  const busy = ref(false);

  async function bootstrap() {
    health.value = await api.fetchHealth();
    projects.value = await api.listProjects();
    if (!currentProjectId.value && projects.value.length) {
      await selectProject(projects.value[0].id);
    }
  }

  async function createProject(name: string) {
    const project = await api.createProject(name, "AI Toy Studio project");
    projects.value = [project, ...projects.value];
    await selectProject(project.id);
  }

  async function removeProject(projectId: string) {
    await api.deleteProject(projectId);
    projects.value = projects.value.filter((item) => item.id !== projectId);
    if (currentProjectId.value !== projectId) return;
    currentModel.value = null;
    models.value = [];
    report.value = null;
    generation.value = null;
    if (projects.value[0]) {
      await selectProject(projects.value[0].id);
    } else {
      currentProjectId.value = null;
    }
  }

  async function selectProject(projectId: string) {
    currentProjectId.value = projectId;
    models.value = await api.listModels(projectId);
    currentModel.value = models.value[0] || null;
    report.value = null;
  }

  async function removeModel(modelId: string) {
    await api.deleteModel(modelId);
    models.value = models.value.filter((item) => item.id !== modelId);
    if (currentModel.value?.id === modelId) {
      currentModel.value = models.value[0] || null;
      report.value = null;
    }
  }

  async function refreshModels() {
    if (!currentProjectId.value) return;
    models.value = await api.listModels(currentProjectId.value);
  }

  async function withBusy<T>(label: string, fn: () => Promise<T>): Promise<T> {
    busy.value = true;
    statusText.value = label;
    try {
      return await fn();
    } finally {
      busy.value = false;
      statusText.value = "就绪";
    }
  }

  async function importFile(file: File, companions: File[] = []) {
    if (!currentProjectId.value) throw new Error("请先创建项目");
    const model = await withBusy("导入模型中…", () =>
      api.importModel(currentProjectId.value!, file, companions),
    );
    await refreshModels();
    currentModel.value = model;
  }

  async function splitCurrent() {
    if (!currentModel.value) return;
    const result = await withBusy("正在按颜色拆分，请稍等…", () =>
      api.splitModel(currentModel.value!.id),
    );
    await refreshModels();
    currentModel.value = result.model;
    return result;
  }

  async function processCurrent(targetHeight = 100, addBase = false) {
    if (!currentModel.value) return;
    const model = await withBusy(`正在标准化到 ${targetHeight} mm，请稍等…`, () =>
      api.processModel(currentModel.value!.id, {
        target_height_mm: targetHeight,
        add_base: addBase,
        base_thickness_mm: 2,
      }),
    );
    await refreshModels();
    currentModel.value = model;
    return model;
  }

  async function validateCurrent() {
    if (!currentModel.value) return;
    const result = await withBusy("网格检查中…", () =>
      api.validateModel(currentModel.value!.id),
    );
    currentModel.value = result.model;
    report.value = result.report;
    await refreshModels();
  }

  async function openColoredCurrent() {
    if (!currentModel.value) return;
    return withBusy("正在生成彩色切片项目…", () => api.openColoredSlicer(currentModel.value!.id));
  }

  async function exportCurrent() {
    if (!currentModel.value) return;
    const result = await withBusy("导出 STL 中…", () => api.exportModel(currentModel.value!.id));
    await refreshModels();
    currentModel.value = result.model;
    return result;
  }

  async function startGeneration(prompt: string, provider?: string) {
    if (!currentProjectId.value) throw new Error("请先创建项目");
    generation.value = await withBusy("提交 AI 生成任务…", () =>
      api.createGeneration(currentProjectId.value!, prompt, provider),
    );
  }

  async function pollGeneration() {
    if (!generation.value) return;
    generation.value = await api.getGeneration(generation.value.id);
  }

  async function downloadGeneration() {
    if (!generation.value) return;
    const result = await withBusy("下载 AI 模型…", () =>
      api.downloadGeneration(generation.value!.id),
    );
    generation.value = result.task;
    await refreshModels();
    currentModel.value = result.model;
  }

  return {
    health,
    projects,
    models,
    currentProjectId,
    currentModel,
    report,
    generation,
    statusText,
    busy,
    bootstrap,
    createProject,
    removeProject,
    selectProject,
    refreshModels,
    removeModel,
    importFile,
    splitCurrent,
    processCurrent,
    validateCurrent,
    openColoredCurrent,
    exportCurrent,
    startGeneration,
    pollGeneration,
    downloadGeneration,
  };
});
