<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import ModelViewport from "@/components/ModelViewport.vue";
import { useStudioStore } from "@/stores/studio";
const store = useStudioStore();
const viewportRef = ref<InstanceType<typeof ModelViewport> | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

const projectName = ref("机械恐龙");
const prompt = ref(
  "设计一个适合 FDM 3D 打印的原创卡通机械恐龙，Q 版圆润，高度约 100mm，实体结构，底部平整，减少悬空。",
);
const provider = ref("meshy");
const targetHeight = ref(100);
const addBase = ref(false);
const clayColor = ref("#f4f1ec");
const leftTab = ref<"model" | "material" | "check">("model");
const tool = ref<"orbit" | "import" | "prompt">("orbit");
const menuOpen = ref(true);
const dragging = ref(false);
const query = ref("");
const message = ref("");
const previewError = ref("");
const previewLoading = ref(false);
const normalizing = ref(false);
const splitting = ref(false);
const splitParts = ref<{ name: string; color: string; faces: number }[]>([]);
const sidebarOpen = ref(true);
const covers = ref<Record<string, string>>({});
const COVER_KEY = "toy-studio-covers";

const currentProject = computed(
  () => store.projects.find((item) => item.id === store.currentProjectId) || null,
);

const visibleModels = computed(() => {
  const text = query.value.trim().toLowerCase();
  if (!text) return store.models;
  return store.models.filter((item) => item.name.toLowerCase().includes(text));
});

const toastText = computed(() => {
  if (store.busy) return store.statusText;
  if (previewLoading.value) return "正在加载模型…";
  if (message.value) return message.value;
  if (previewError.value) return previewError.value;
  if (store.generation?.status) {
    return `生成任务 ${store.generation.status}${
      store.generation.error_message ? " · " + store.generation.error_message : ""
    }`;
  }
  if (store.currentModel) return `已打开 ${store.currentModel.name}`;
  return "拖入参考图或模型，开始玩具设计";
});

const toastTone = computed(() => {
  if (store.busy || previewLoading.value) return "busy";
  if (previewError.value || store.generation?.status === "FAILED") return "error";
  if (store.report?.status === "WARNING" || store.report?.status === "ERROR") {
    return store.report.status === "ERROR" ? "error" : "warn";
  }
  return "ok";
});

onMounted(async () => {
  try {
    covers.value = JSON.parse(localStorage.getItem(COVER_KEY) || "{}");
  } catch {
    covers.value = {};
  }
  try {
    await store.bootstrap();
  } catch (error) {
    message.value = error instanceof Error ? error.message : String(error);
  }
});

function rememberCover(payload: { id: string; url: string }) {
  covers.value = { ...covers.value, [payload.id]: payload.url };
  try {
    localStorage.setItem(COVER_KEY, JSON.stringify(covers.value));
  } catch {
    // 封面只留在当前页面，避免把本地存储写满。
  }
}

function cardBadge(sourceType: string) {
  if (sourceType === "split") return "拆分";
  if (sourceType === "processed" || sourceType === "export") return "加工";
  if (sourceType === "import") return "上传";
  return "模型";
}

async function run(action: () => Promise<unknown>) {
  message.value = "";
  try {
    await action();
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    message.value =
      (typeof detail === "string" ? detail : detail?.message) ||
      error?.message ||
      String(error);
  }
}

const MODEL_FILE = /\.(stl|obj|glb|gltf)$/i;

async function missingGltfFiles(file: File, companions: File[]) {
  if (!file.name.toLowerCase().endsWith(".gltf")) return [];
  let payload: { buffers?: { uri?: string }[]; images?: { uri?: string }[] };
  try {
    payload = JSON.parse(await file.text());
  } catch {
    return [];
  }
  const names = new Set(companions.map((item) => item.name.toLowerCase()));
  const missing: string[] = [];
  for (const group of [payload.buffers, payload.images]) {
    for (const item of group || []) {
      const uri = item?.uri;
      if (!uri || uri.startsWith("data:") || uri.includes("://")) continue;
      const clean = uri.split("?")[0].split("#")[0];
      const base = clean.split("/").pop()?.toLowerCase() || "";
      if (!names.has(base)) missing.push(clean);
    }
  }
  return missing;
}

async function useFiles(files: File[]) {
  const model = files.find((item) => MODEL_FILE.test(item.name));
  if (!model) {
    message.value = "请上传 STL、OBJ、GLB 或 GLTF。GLTF 要连同旁边的 .bin 一起选。";
    return;
  }
  const companions = files.filter((item) => item !== model);
  const missing = await missingGltfFiles(model, companions);
  if (missing.length) {
    message.value = `这个 GLTF 还依赖 ${missing.join("、")}。请在文件选择框里和 .gltf 一起选中后再上传。`;
    return;
  }
  await run(() => store.importFile(model, companions));
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = [...(input.files || [])];
  input.value = "";
  if (files.length) await useFiles(files);
}

function onDrop(event: DragEvent) {
  dragging.value = false;
  const files = [...(event.dataTransfer?.files || [])];
  if (files.length) void useFiles(files);
}

function formatMm(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(1);
}

function applyColor() {
  viewportRef.value?.setColor(clayColor.value);
}

async function removePage(projectId: string, name: string) {
  await run(async () => {
    await store.removeProject(projectId);
    message.value = `已删除页面 ${name}`;
  });
}

async function removeSceneModel(modelId: string, name: string) {
  await run(async () => {
    await store.removeModel(modelId);
    message.value = `已从场景删除 ${name}`;
  });
}

async function normalize() {
  normalizing.value = true;
  try {
    await run(async () => {
      const model = await store.processCurrent(targetHeight.value, addBase.value);
      if (!model) return;
      message.value = `标准化完成：${formatMm(model.width_mm)} × ${formatMm(model.depth_mm)} × ${formatMm(model.height_mm)} mm`;
    });
  } finally {
    normalizing.value = false;
  }
}

async function generate() {
  leftTab.value = "model";
  await run(() => store.startGeneration(prompt.value, provider.value));
}

async function splitColors() {
  if (!store.currentModel) return;
  splitting.value = true;
  try {
    await run(async () => {
      const result = await store.splitCurrent();
      if (!result) return;
      splitParts.value = result.parts;
      const how = result.mode === "material" ? "按颜色" : result.mode === "loose" ? "按分开的零件" : "按整体";
      message.value = `已${how}拆成 ${result.parts.length} 块，并平铺在视口里`;
    });
  } finally {
    splitting.value = false;
  }
}

async function sendToPrint() {
  if (!store.currentModel) return;
  await run(async () => {
    const result = await store.openColoredCurrent();
    if (!result) return;
    const slots = result.slots.map((slot) => `${slot.slot} ${slot.name} ${slot.color}`).join("、");
    const merged =
      result.source_colors > result.slots.length
        ? `模型有 ${result.source_colors} 种颜色，A1 只有 4 个料槽，已合并成 ${result.slots.length} 色。`
        : "";
    message.value = `已用 ${result.slots.length} 色打开 Bambu Studio。${merged}料槽：${slots}。尚未切片，也没有发送到打印机。`;
  });
}

function statusDot(status?: string | null) {
  if (!status) return "";
  if (status === "ERROR") return "error";
  if (status === "WARNING") return "warn";
  return "ok";
}
</script>

<template>
  <div class="shell">
    <div class="workspace" :class="{ 'is-collapsed': !sidebarOpen }">
      <aside class="dock" :class="{ 'is-collapsed': !sidebarOpen }">
        <div v-if="!sidebarOpen" class="rail">
          <button class="rail-btn" title="展开侧边栏" @click="sidebarOpen = true">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5 3.2 8.8 7 5 10.8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
          <button class="rail-btn accent" title="上传模型" @click="fileInput?.click()">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 10.5V3.5M4.2 6.2 7 3.4 9.8 6.2M3 11.6h8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
        </div>
        <div class="dock-scroll">
          <div class="project-head">
            <div class="mark" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 1.2 9.3 6.7 14.8 8 9.3 9.3 8 14.8 6.7 9.3 1.2 8 6.7 6.7 8 1.2Z" fill="#f4f4f4"/>
              </svg>
            </div>
            <div class="project-copy">
              <h1>{{ currentProject?.name || "未命名项目" }}</h1>
              <p>3D 工作台 · V0.3</p>
            </div>
            <button class="collapse-btn" title="收起侧边栏" @click="sidebarOpen = false">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9 3.2 5.2 7 9 10.8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>

          <div class="page-switch">
            <div
              v-for="project in store.projects"
              :key="project.id"
              class="page-chip"
              :class="{ active: project.id === store.currentProjectId }"
            >
              <button type="button" class="page-name" @click="run(() => store.selectProject(project.id))">
                {{ project.name }}
              </button>
              <button
                type="button"
                class="page-delete"
                title="删除页面"
                @click.stop.prevent="removePage(project.id, project.name)"
              >
                ×
              </button>
            </div>
          </div>
          <div class="row-actions page-create">
            <input v-model="projectName" placeholder="新页面名称" />
            <button class="ghost" type="button" style="flex: none; padding: 0 12px" :disabled="store.busy" @click="run(() => store.createProject(projectName))">
              新建
            </button>
          </div>

          <div class="segment">
            <button type="button" :class="{ active: leftTab === 'model' }" @click="leftTab = 'model'">场景</button>
            <button type="button" :class="{ active: leftTab === 'material' }" @click="leftTab = 'material'">材质</button>
            <button type="button" :class="{ active: leftTab === 'check' }" @click="leftTab = 'check'">检查</button>
          </div>

          <template v-if="leftTab === 'model'">
            <div class="library-tools">
              <label class="library-search">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="6" cy="6" r="4.2" stroke="currentColor" stroke-width="1.3"/>
                  <path d="M9.2 9.2 12 12" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                </svg>
                <input v-model="query" placeholder="搜索场景" />
              </label>
              <button type="button" class="upload-btn" @click="fileInput?.click()">上传</button>
            </div>
            <div
              class="scene-grid"
              :class="{ hot: dragging }"
              @dragover.prevent="dragging = true"
              @dragleave="dragging = false"
              @drop.prevent="onDrop"
            >
              <article
                v-for="model in visibleModels"
                :key="model.id"
                class="model-card"
                :class="{ active: model.id === store.currentModel?.id }"
                @click="store.currentModel = model"
              >
                <img v-if="covers[model.id]" :src="covers[model.id]" :alt="model.name" />
                <div v-else class="cover-fallback">{{ model.format.toUpperCase() }}</div>
                <span class="card-badge">{{ cardBadge(model.source_type) }}</span>
                <button
                  type="button"
                  class="card-delete"
                  title="删除"
                  @click.stop.prevent="removeSceneModel(model.id, model.name)"
                >
                  ×
                </button>
                <div class="card-name">
                  <strong>{{ model.name }}</strong>
                  <small>v{{ model.version }}</small>
                </div>
              </article>
              <div v-if="!visibleModels.length" class="hint card-empty">还没有模型，点右上角上传</div>
            </div>
          </template>

          <template v-else-if="leftTab === 'material'">
            <div class="section-label"><span>预览材质</span></div>
            <div class="swatch-row">
              <span>黏土色</span>
              <input class="swatch" type="color" v-model="clayColor" @input="applyColor" />
            </div>
            <p class="hint">GLB 会保留模型自带的颜色和材质。STL 文件本身没有材质，所以只能显示成单色。</p>
            <div class="section-label"><span>打印材料</span></div>
            <select class="select">
              <option>PLA · 0.4mm 喷嘴</option>
              <option>PETG · 0.4mm 喷嘴</option>
              <option>TPU · 0.4mm 喷嘴</option>
            </select>
          </template>

          <template v-else>
            <div class="section-label"><span>打印约束</span></div>
            <div class="stats">
              <div class="stat"><span>目标高度</span><b>{{ targetHeight }} mm</b></div>
              <div class="stat"><span>热床余量</span><b>240 mm</b></div>
            </div>
            <label class="toggle-row" style="margin-top: 12px">
              <span>增加平底底座</span>
              <input v-model="addBase" type="checkbox" />
            </label>
            <button class="primary" :disabled="!store.currentModel || store.busy" @click="normalize">
              {{ normalizing ? "正在标准化…" : "标准化尺寸" }}
            </button>
            <button class="ghost" style="width: 100%; margin-top: 8px" :disabled="!store.currentModel || store.busy" @click="run(() => store.validateCurrent())">
              运行网格检查
            </button>
            <ul class="checks" style="margin-top: 12px">
              <li v-if="!store.report">还没有检查报告</li>
              <li v-for="(item, index) in store.report?.recommendations || []" :key="index">{{ item }}</li>
              <li v-if="store.report && !(store.report.recommendations || []).length">未发现需要处理的问题</li>
            </ul>
          </template>
          <input
            ref="fileInput"
            hidden
            type="file"
            accept=".stl,.obj,.glb,.gltf,.bin,.png,.jpg,.jpeg,.webp"
            multiple
            @change="onFileChange"
          />
        </div>

      </aside>

      <section class="stage">
        <ModelViewport
          ref="viewportRef"
          :model="store.currentModel"
          @error="previewError = $event"
          @loading="previewLoading = $event"
          @cover="rememberCover"
        />

        <div v-if="!store.currentModel" class="empty-hint">
          <div>
            <strong>把玩具放进视口</strong>
            <span>上传 STL / GLB。GLTF 要连同 .bin 一起选</span>
          </div>
        </div>

        <div class="toast">
          <i class="pulse" :class="toastTone"></i>
          <span>{{ toastText }}</span>
        </div>

        <div v-if="menuOpen" class="add-menu">
          <header>ADD</header>
          <button class="tool" :class="{ active: tool === 'orbit' }" @click="tool = 'orbit'">
            <span>旋转查看</span><i></i>
          </button>
          <button class="tool" :class="{ active: tool === 'import' }" @click="tool = 'import'; fileInput?.click()">
            <span>导入模型</span><i></i>
          </button>
        </div>

        <div class="stage-tools">
          <button class="icon-btn" :class="{ active: menuOpen }" title="工具" @click="menuOpen = !menuOpen">+</button>
          <button class="icon-btn" title="导入" @click="fileInput?.click()">
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M7.5 2v8M4 6.5 7.5 10 11 6.5M3 12.5h9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
          </button>
          <button class="icon-btn" title="检查" @click="run(() => store.validateCurrent())">
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M3 8.2 6.1 11 12 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
          </button>
          <button class="icon-btn" title="导出" @click="run(() => store.exportCurrent())">
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M7.5 10V2M4 6.5 7.5 3 11 6.5M3 12.5h9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
          </button>
        </div>
      </section>

      <aside class="dock right">
        <div class="dock-scroll">
          <div class="section-label"><span>打印</span></div>
            <div class="split-card">
              <div class="split-flow" aria-hidden="true">
                <div class="split-thumb">
                  <i class="blob gray"></i>
                </div>
                <span class="split-arrow">→</span>
                <div class="split-thumb">
                  <i class="blob hair"></i>
                  <i class="blob shirt"></i>
                  <i class="blob pants"></i>
                </div>
                <span class="split-arrow">→</span>
                <div class="split-thumb tray">
                  <i></i><i></i><i></i><i></i><i></i><i></i>
                </div>
              </div>
              <p>按颜色拆开并平铺。同一种颜色收成一块，方便后面分色打印。</p>
              <button class="split-btn" type="button" :disabled="!store.currentModel || store.busy" @click="splitColors">
                {{ splitting ? "正在拆分…" : "拆分" }}
              </button>
              <div v-if="splitParts.length" class="split-parts">
                <span v-for="part in splitParts" :key="part.name + part.color">
                  <i :style="{ background: part.color }"></i>{{ part.name }}
                </span>
              </div>
            </div>
            <div class="block" style="border-top: 0">
              <h3>加工</h3>
              <div class="field">
                <label>目标高度 mm</label>
                <input v-model.number="targetHeight" type="number" min="20" max="240" />
              </div>
              <label class="toggle-row">
                <span>平底底座</span>
                <input v-model="addBase" type="checkbox" />
              </label>
              <button class="ghost" style="width: 100%" :disabled="!store.currentModel || store.busy" @click="normalize">
                {{ normalizing ? "正在标准化…" : "Blender 标准化" }}
              </button>
              <button class="ghost" style="width: 100%; margin-top: 8px" :disabled="!store.currentModel || store.busy" @click="run(() => store.validateCurrent())">
                网格检查
              </button>
            </div>
            <div class="block">
              <h3>检查</h3>
              <div class="swatch-row">
                <span>状态</span>
                <b>{{ store.currentModel?.check_status || store.report?.status || "未检查" }}</b>
              </div>
              <ul class="checks">
                <li v-if="!(store.report?.recommendations || []).length">暂无建议</li>
                <li v-for="(item, index) in store.report?.recommendations || []" :key="index">{{ item }}</li>
              </ul>
            </div>

          <p class="footer-note">生成带颜色的 3MF 并打开 Bambu Studio。A1 最多 4 色，相近颜色会合并。不会自动切片，也不会发送到打印机。</p>
          <button class="wide" :disabled="!store.currentModel || store.busy" @click="sendToPrint">
            导出并打开切片
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>
