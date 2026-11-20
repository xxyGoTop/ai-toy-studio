import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

export interface MeshStats {
  polygons: number;
  vertices: number;
}

export class ModelViewer {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private ortho: THREE.OrthographicCamera;
  private controls: OrbitControls;
  private root = new THREE.Group();
  private grid: THREE.GridHelper;
  private axes: THREE.AxesHelper;
  private clay: THREE.MeshStandardMaterial;
  private animationId = 0;
  private disposed = false;
  private useOrtho = false;
  private resizeObserver: ResizeObserver;

  constructor(private container: HTMLElement) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#101113");
    this.scene.fog = new THREE.Fog("#101113", 1.4, 6);

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;
    this.camera = new THREE.PerspectiveCamera(38, width / height, 0.01, 100);
    this.camera.position.set(0.42, 0.28, 0.62);

    const aspect = width / Math.max(height, 1);
    this.ortho = new THREE.OrthographicCamera(-aspect, aspect, 1, -1, 0.01, 100);
    this.ortho.position.copy(this.camera.position);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(width, height);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.target.set(0, 0, 0);

    const hemi = new THREE.HemisphereLight(0xffffff, 0x1a1c20, 1.35);
    const key = new THREE.DirectionalLight(0xffffff, 2.1);
    key.position.set(1.6, 2.4, 1.2);
    const fill = new THREE.DirectionalLight(0xd7e4ff, 0.7);
    fill.position.set(-1.8, 0.8, -0.6);
    const rim = new THREE.DirectionalLight(0xffffff, 0.55);
    rim.position.set(0, 1.2, -2);
    this.scene.add(hemi, key, fill, rim);

    this.grid = new THREE.GridHelper(1, 28, 0x3c414a, 0x24282f);
    this.grid.position.y = -0.08;
    this.scene.add(this.grid);

    this.axes = new THREE.AxesHelper(0.08);
    this.axes.visible = false;
    this.root.add(this.axes);
    this.scene.add(this.root);

    this.clay = new THREE.MeshStandardMaterial({
      color: 0xf4f1ec,
      roughness: 0.38,
      metalness: 0.04,
    });

    this.resizeObserver = new ResizeObserver(() => this.onResize());
    this.resizeObserver.observe(container);
    this.animate();
  }

  private onResize = () => {
    if (this.disposed) return;
    const width = this.container.clientWidth;
    const height = Math.max(this.container.clientHeight, 1);
    const aspect = width / height;
    this.camera.aspect = aspect;
    this.camera.updateProjectionMatrix();
    this.ortho.left = -aspect;
    this.ortho.right = aspect;
    this.ortho.top = 1;
    this.ortho.bottom = -1;
    this.ortho.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  };

  private activeCamera() {
    return this.useOrtho ? this.ortho : this.camera;
  }

  setProjection(mode: "perspective" | "orthographic") {
    this.useOrtho = mode === "orthographic";
    const next = this.activeCamera();
    next.position.copy(this.camera.position);
    this.controls.object = next;
    this.controls.update();
  }

  setColor(hex: string) {
    this.clay.color.set(hex);
    const color = new THREE.Color(hex);
    this.root.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => {
        if (material && "color" in material) material.color.copy(color);
      });
    });
  }

  private animate = () => {
    if (this.disposed) return;
    this.animationId = requestAnimationFrame(this.animate);
    if (this.useOrtho) this.ortho.position.copy(this.camera.position);
    this.controls.update();
    this.renderer.render(this.scene, this.activeCamera());
  };

  clear() {
    const leftovers = this.root.children.filter((child) => child !== this.axes);
    leftovers.forEach((child) => this.root.remove(child));
    this.axes.visible = false;
  }

  async load(url: string, format: string): Promise<MeshStats> {
    this.clear();
    const lower = format.toLowerCase();
    let object: THREE.Object3D | null = null;

    if (lower === "glb" || lower === "gltf") {
      const gltf = await new GLTFLoader().loadAsync(url);
      object = gltf.scene;
    } else if (lower === "obj") {
      object = await new OBJLoader().loadAsync(url);
    } else if (lower === "stl") {
      const geometry = await new STLLoader().loadAsync(url);
      geometry.computeVertexNormals();
      object = new THREE.Mesh(geometry, this.clay);
    } else {
      throw new Error(`浏览器暂不直接预览 .${format}，请先导出 STL/GLB`);
    }

    this.root.add(object);
    this.axes.visible = true;
    const stats = this.measure(object);
    this.fitCamera(object);
    return stats;
  }

  private frameMeshes(object: THREE.Object3D) {
    object.updateWorldMatrix(true, true);
    const items: { mesh: THREE.Mesh; box: THREE.Box3; max: number }[] = [];
    object.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      child.visible = true;
      const box = new THREE.Box3().setFromObject(child);
      if (box.isEmpty()) return;
      const size = box.getSize(new THREE.Vector3());
      const max = Math.max(size.x, size.y, size.z);
      if (!Number.isFinite(max) || max <= 1e-6) return;
      items.push({ mesh: child, box, max });
    });
    if (!items.length) return new THREE.Box3();

    const sorted = items.map((item) => item.max).sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    const p90 = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.9))];
    // 只拿掉比模型本体大一个数量级的影棚地面。车架、水带、卷帘门这类长零件要留下来。
    const backdropLimit = Math.max(p90 * 12, median * 40, 1);

    const box = new THREE.Box3();
    let kept = 0;
    items.forEach((item) => {
      if (this.isBackdrop(item.mesh, item.box, item.max, backdropLimit)) {
        item.mesh.visible = false;
        return;
      }
      box.union(item.box);
      kept += 1;
    });
    if (!kept) items.forEach((item) => box.union(item.box));
    return box;
  }

  private isBackdrop(mesh: THREE.Mesh, box: THREE.Box3, max: number, limit: number) {
    const name = `${mesh.name} ${mesh.parent?.name || ""}`.toLowerCase();
    const namedGround =
      name.includes("地面") || name.includes("ground") || name.includes("floor");
    const size = box.getSize(new THREE.Vector3());
    const horizontal = Math.max(size.x, size.z);
    const flat = size.y < horizontal * 0.04 && horizontal > 0.3;
    if (namedGround && (flat || max > limit * 0.25)) return true;
    return flat && max > limit;
  }

  private measure(object: THREE.Object3D): MeshStats {
    let polygons = 0;
    let vertices = 0;
    object.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      const geometry = child.geometry as THREE.BufferGeometry;
      const position = geometry.getAttribute("position");
      vertices += position?.count || 0;
      if (geometry.index) polygons += geometry.index.count / 3;
      else polygons += (position?.count || 0) / 3;
    });
    return { polygons: Math.round(polygons), vertices };
  }

  private fitCamera(object: THREE.Object3D) {
    const box = this.frameMeshes(object);
    if (box.isEmpty()) return;

    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const holder = new THREE.Group();
    object.parent?.add(holder);
    holder.attach(object);
    holder.position.sub(center);

    const maxDim = Math.max(size.x, size.y, size.z) || 0.1;
    const distance = maxDim * 2.35;
    this.camera.near = Math.max(distance / 200, 0.001);
    this.camera.far = Math.max(distance * 30, 100);
    this.camera.updateProjectionMatrix();
    this.ortho.near = this.camera.near;
    this.ortho.far = this.camera.far;
    const aspect = this.camera.aspect || 1;
    const half = maxDim * 1.15;
    this.ortho.left = -half * aspect;
    this.ortho.right = half * aspect;
    this.ortho.top = half;
    this.ortho.bottom = -half;
    this.ortho.updateProjectionMatrix();
    this.camera.position.set(distance * 0.85, distance * 0.55, distance);
    this.ortho.position.copy(this.camera.position);
    const span = Math.max(size.x, size.z, 0.2) * 6;
    this.grid.scale.set(span, 1, span);
    this.grid.position.y = -size.y / 2;
    this.axes.scale.setScalar(Math.max(maxDim * 2.4, 0.05));
    this.scene.fog = new THREE.Fog("#101113", distance * 3.5, distance * 12);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  captureCover(size = 360) {
    const axesVisible = this.axes.visible;
    const gridVisible = this.grid.visible;
    this.axes.visible = false;
    this.grid.visible = false;
    this.renderer.render(this.scene, this.activeCamera());
    const source = this.renderer.domElement;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    if (!context) return "";
    const side = Math.min(source.width, source.height);
    const sx = (source.width - side) / 2;
    const sy = (source.height - side) / 2;
    context.drawImage(source, sx, sy, side, side, 0, 0, size, size);
    this.axes.visible = axesVisible;
    this.grid.visible = gridVisible;
    return canvas.toDataURL("image/jpeg", 0.72);
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.animationId);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.renderer.dispose();
    this.clay.dispose();
    if (this.renderer.domElement.parentElement === this.container) {
      this.container.removeChild(this.renderer.domElement);
    }
  }
}
