<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ModelAsset } from "@/types";
import { modelFileUrl } from "@/api/client";
import { ModelViewer, type MeshStats } from "@/three/viewer";

const props = defineProps<{
  model: ModelAsset | null;
}>();

const emit = defineEmits<{
  stats: [MeshStats | null];
  error: [string];
  loading: [boolean];
  cover: [{ id: string; url: string }];
}>();

const host = ref<HTMLElement | null>(null);
let viewer: ModelViewer | null = null;

onMounted(() => {
  if (!host.value) return;
  viewer = new ModelViewer(host.value);
  if (props.model) void loadModel(props.model);
});

onBeforeUnmount(() => {
  viewer?.dispose();
  viewer = null;
});

async function loadModel(model: ModelAsset) {
  if (!viewer) return;
  emit("loading", true);
  try {
    if (model.format === "blend") {
      viewer.clear();
      emit("stats", null);
      emit("error", "Blend 工程需先导出 STL / GLB 再预览");
      return;
    }
    const stats = await viewer.load(modelFileUrl(model), model.format);
    emit("stats", stats);
    emit("error", "");
    const cover = viewer.captureCover();
    if (cover) emit("cover", { id: model.id, url: cover });
  } catch (error) {
    emit("stats", null);
    const raw = error instanceof Error ? error.message : String(error);
    const missing = raw.match(/Failed to load buffer "([^"]+)"/);
    emit(
      "error",
      missing
        ? `GLTF 缺少外部文件 ${missing[1]}。请把 .gltf 和这个文件一起重新上传。`
        : raw,
    );
  } finally {
    emit("loading", false);
  }
}

function setColor(hex: string) {
  viewer?.setColor(hex);
}

function setProjection(mode: "perspective" | "orthographic") {
  viewer?.setProjection(mode);
}

defineExpose({ setColor, setProjection });

watch(
  () => props.model?.id,
  () => {
    if (props.model) void loadModel(props.model);
    else {
      viewer?.clear();
      emit("stats", null);
    }
  },
);
</script>

<template>
  <div class="viewport" ref="host"></div>
</template>
