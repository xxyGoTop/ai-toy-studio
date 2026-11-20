<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ModelAsset } from "@/types";
import { modelFileUrl } from "@/api/client";
import { ModelViewer } from "@/three/viewer";

const props = defineProps<{
  model: ModelAsset | null;
  statusText: string;
}>();

const host = ref<HTMLElement | null>(null);
let viewer: ModelViewer | null = null;
const previewError = ref("");

onMounted(() => {
  if (host.value) {
    viewer = new ModelViewer(host.value);
    if (props.model) void loadModel(props.model);
  }
});

onBeforeUnmount(() => {
  viewer?.dispose();
  viewer = null;
});

async function loadModel(model: ModelAsset) {
  if (!viewer) return;
  previewError.value = "";
  try {
    if (model.format === "blend") {
      previewError.value = "Blend 工程文件需先导出 STL/GLB 后再预览";
      viewer.clear();
      return;
    }
    await viewer.load(modelFileUrl(model), model.format);
  } catch (error) {
    previewError.value = error instanceof Error ? error.message : String(error);
  }
}

watch(
  () => props.model?.id,
  () => {
    if (props.model) void loadModel(props.model);
  },
);
</script>

<template>
  <div class="viewport" ref="host">
    <div class="status-line">
      <span v-if="previewError">{{ previewError }}</span>
      <span v-else>{{ statusText }}</span>
    </div>
  </div>
</template>
