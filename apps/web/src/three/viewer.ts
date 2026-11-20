import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

export class ModelViewer {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private root = new THREE.Group();
  private animationId = 0;
  private disposed = false;

  constructor(private container: HTMLElement) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#0b1016");

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000);
    this.camera.position.set(0.25, 0.2, 0.35);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(width, height);
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;

    const hemi = new THREE.HemisphereLight(0xffffff, 0x223344, 1.1);
    const dir = new THREE.DirectionalLight(0xffffff, 1.2);
    dir.position.set(2, 3, 1);
    this.scene.add(hemi, dir, this.root);

    const grid = new THREE.GridHelper(0.4, 20, 0x3a4a5e, 0x243142);
    this.scene.add(grid);

    window.addEventListener("resize", this.onResize);
    this.animate();
  }

  private onResize = () => {
    if (this.disposed) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / Math.max(height, 1);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  };

  private animate = () => {
    if (this.disposed) return;
    this.animationId = requestAnimationFrame(this.animate);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  };

  clear() {
    while (this.root.children.length) {
      const child = this.root.children.pop();
      if (child) this.root.remove(child);
    }
  }

  async load(url: string, format: string) {
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
      const material = new THREE.MeshStandardMaterial({
        color: 0x8ab4ff,
        metalness: 0.1,
        roughness: 0.45,
      });
      object = new THREE.Mesh(geometry, material);
    } else {
      throw new Error(`浏览器暂不直接预览 .${format}，请先导出 STL/GLB`);
    }

    this.root.add(object);
    this.fitCamera(object);
  }

  private fitCamera(object: THREE.Object3D) {
    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    object.position.sub(center);

    const maxDim = Math.max(size.x, size.y, size.z) || 0.1;
    const distance = maxDim * 2.2;
    this.camera.position.set(distance, distance * 0.7, distance);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.animationId);
    window.removeEventListener("resize", this.onResize);
    this.controls.dispose();
    this.renderer.dispose();
    if (this.renderer.domElement.parentElement === this.container) {
      this.container.removeChild(this.renderer.domElement);
    }
  }
}
