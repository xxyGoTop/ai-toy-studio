<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import ModelViewport from "@/components/ModelViewport.vue";
import { createPrintJob, openSlicer } from "@/api/client";
import { useStudioStore } from "@/stores/studio";

const store = useStudioStore();
const projectName = ref("机械恐龙玩具");
const prompt = ref(
  "设计一个适合 FDM 3D 打印的原创卡通机械恐龙玩具，Q版圆润，高度约100mm，实体结构，底部平整，减少悬空。",
);
const targetHeight = ref(100);
const addBase = ref(false);
const message = ref("");

const currentProject = computed(() =>
  store.projects.find((item) => item.id === store.currentProjectId) || null,
);

onMounted(async () => {
  try {
    await store.bootstrap();
  } catch (error) {
    message.value = error instanceof Error ? error.message : String(error);
  }
});

async function run(action: () => Promise<unknown>) {
  message.value = "";
  try {
    await action();
  } catch (error: any) {
    message.value =
      error?.response?.data?.detail?.message ||
      error?.response?.data?.detail ||
      error?.message ||
      String(error);
  }
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  await run(() => store.importFile(file));
  input.value = "";
}

async function sendToPrint() {
  if (!store.currentModel) return;
  await run(async () => {
    const exported = await store.exportCurrent();
    if (!exported) return;
    const job = await createPrintJob(exported.model.id);
    const slicer = await openSlicer(job.id);
    message.value = slicer.opened
      ? `已尝试打开 Bambu Studio：${slicer.model_path}`
      : `${slicer.message || "请手动导入"}：${slicer.model_path}`;
  });
}
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">AI 3D Toy Studio · Bambu A1</div>
      <div class="muted">
        Blender:
        <span :class="store.health?.blender_exists ? 'badge ok' : 'badge error'">
          {{ store.health?.blender_exists ? "已连接" : "未找到" }}
        </span>
        · Provider: {{ store.health?.ai_provider || "-" }}
      </div>
    </header>

    <aside class="side">
      <div class="panel-title">项目</div>
      <div class="card stack">
        <input v-model="projectName" placeholder="新项目名称" />
        <button class="primary" :disabled="store.busy" @click="run(() => store.createProject(projectName))">
          新建项目
        </button>
      </div>

      <div
        v-for="project in store.projects"
        :key="project.id"
        class="list-item"
        :class="{ active: project.id === store.currentProjectId }"
        @click="run(() => store.selectProject(project.id))"
      >
        <div>{{ project.name }}</div>
        <div class="muted">{{ project.id.slice(0, 8) }}</div>
      </div>

      <div class="panel-title">模型库</div>
      <div
        v-for="model in store.models"
        :key="model.id"
        class="list-item"
        :class="{ active: model.id === store.currentModel?.id }"
        @click="store.currentModel = model"
      >
        <div>{{ model.name }}</div>
        <div class="muted">
          {{ model.format.toUpperCase() }} · v{{ model.version }} · {{ model.source_type }}
          <span v-if="model.check_status" class="badge" :class="model.check_status.toLowerCase()">
            {{ model.check_status }}
          </span>
        </div>
      </div>
    </aside>

    <main>
      <ModelViewport :model="store.currentModel" :status-text="store.statusText" />
    </main>

    <aside class="right">
      <div class="panel-title">创作入口</div>
      <div class="card stack">
        <div class="field">
          <label>当前项目</label>
          <div>{{ currentProject?.name || "未选择" }}</div>
        </div>
        <div class="field">
          <label>导入 STL / OBJ / GLB</label>
          <input type="file" accept=".stl,.obj,.glb,.gltf" @change="onFileChange" />
        </div>
        <div class="field">
          <label>AI 文字生成 Prompt</label>
          <textarea v-model="prompt" />
        </div>
        <button :disabled="store.busy" @click="run(() => store.startGeneration(prompt))">提交 AI 生成</button>
        <div v-if="store.generation" class="muted">
          任务 {{ store.generation.status }}
          <span v-if="store.generation.error_message"> · {{ store.generation.error_message }}</span>
        </div>
        <div class="row">
          <button :disabled="!store.generation || store.busy" @click="run(() => store.pollGeneration())">
            刷新状态
          </button>
          <button :disabled="!store.generation || store.busy" @click="run(() => store.downloadGeneration())">
            下载模型
          </button>
        </div>
      </div>

      <div class="panel-title">Blender 加工</div>
      <div class="card stack">
        <div class="field">
          <label>目标高度 (mm)</label>
          <input v-model.number="targetHeight" type="number" min="10" max="240" />
        </div>
        <label class="row">
          <input v-model="addBase" type="checkbox" />
          增加打印底座
        </label>
        <button
          class="primary"
          :disabled="!store.currentModel || store.busy"
          @click="run(() => store.processCurrent(targetHeight, addBase))"
        >
          标准化处理
        </button>
        <button :disabled="!store.currentModel || store.busy" @click="run(() => store.validateCurrent())">
          网格检查
        </button>
        <button :disabled="!store.currentModel || store.busy" @click="run(() => store.exportCurrent())">
          导出 STL
        </button>
        <button :disabled="!store.currentModel || store.busy" @click="sendToPrint">
          导出并打开切片
        </button>
      </div>

      <div class="panel-title">检查报告</div>
      <div class="card">
        <div v-if="!store.report" class="muted">尚未检查</div>
        <template v-else>
          <div class="badge" :class="store.report.status.toLowerCase()">{{ store.report.status }}</div>
          <div class="muted" style="margin-top: 8px">
            尺寸:
            {{ store.report.dimensions_mm?.x?.toFixed?.(1) }} ×
            {{ store.report.dimensions_mm?.y?.toFixed?.(1) }} ×
            {{ store.report.dimensions_mm?.z?.toFixed?.(1) }} mm
          </div>
          <ul>
            <li v-for="(item, index) in store.report.recommendations || []" :key="index">{{ item }}</li>
          </ul>
        </template>
      </div>

      <div v-if="message" class="card">
        <div class="panel-title">消息</div>
        <div>{{ message }}</div>
      </div>
    </aside>
  </div>
</template>
