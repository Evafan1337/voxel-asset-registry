// Reference Lab viewer: one reference (left) and optionally one character (right) in the same scene —
// one orthographic camera, one ground, one light, rest pose (no clip plays), so scale and silhouette compare.

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { disposeModelResources } from "./toon";

export type DisplayMode = "solid" | "wire" | "solidwire" | "normals" | "armature" | "weights";
export type CompareMode = "single" | "side" | "overlay" | "silhouette" | "wire";
export type LabPreset = "front" | "34" | "side" | "back";

export interface LabMeshInfo {
  name: string;
  side: "left" | "right";
  verts: number;
  edges: number;
  tris: number;
  size: [number, number, number];
  materials: string[];
  skinned: boolean;
  bones: number;           // bones of the skeleton
  groups: number;          // bones that actually weigh vertices (vertex groups in Blender terms)
  maxInfluences: number;   // most bones on one vertex
  colors: boolean;         // carries vertex colours (regions / palette)
  visible: boolean;
}

// glTF axes: +Y up, the character faces +Z
const DIRECTIONS: Record<LabPreset, THREE.Vector3> = {
  front: new THREE.Vector3(0, 0, 1),
  "34": new THREE.Vector3(0.62, 0.3, 1).normalize(),
  side: new THREE.Vector3(1, 0, 0),
  back: new THREE.Vector3(0, 0, -1),
};
const LEFT_COLOR = new THREE.Color("#e8823a");
const RIGHT_COLOR = new THREE.Color("#3a8ee8");
const loader = new GLTFLoader();

function cssVar(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function heat(w: number): THREE.Color {
  // 0 blue → 0.5 green → 1 red, like Blender weight paint
  const c = new THREE.Color();
  c.setHSL((1 - Math.min(Math.max(w, 0), 1)) * 0.66, 0.9, 0.5);
  return c;
}

interface Side {
  root: THREE.Object3D;
  meshes: THREE.Mesh[];
  helper: THREE.SkeletonHelper | null;
  width: number;
}

export class LabViewer {
  readonly el: HTMLElement;
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 100);
  private controls: OrbitControls;
  private ground: THREE.Mesh;
  private grid: THREE.GridHelper;
  private left: Side | null = null;
  private right: Side | null = null;
  private overlays: THREE.Object3D[] = [];
  private made: THREE.Material[] = [];          // materials created for the current mode, freed on refresh
  private resizeObserver: ResizeObserver;
  private intersectionObserver: IntersectionObserver;
  private visible = true;
  private needsRender = true;
  private contextLost = false;
  private frameId = 0;
  private disposed = false;
  private token = 0;
  private viewHeight = 2.2;

  display: DisplayMode = "solid";
  compare: CompareMode = "single";
  opacity = 0.5;
  weightBone = "";

  constructor(container: HTMLElement) {
    this.el = container;
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.domElement.classList.add("viewer-canvas");
    container.appendChild(this.renderer.domElement);
    this.renderer.domElement.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      this.contextLost = true;
    });
    this.renderer.domElement.addEventListener("webglcontextrestored", () => {
      this.contextLost = false;
      this.needsRender = true;
    });
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.controls.addEventListener("change", () => { this.needsRender = true; });
    const hemi = new THREE.HemisphereLight(0xffffff, 0x6b6660, 1.7);
    const sun = new THREE.DirectionalLight(0xffffff, 2.0);
    sun.position.set(-0.45, 0.7, 0.55).multiplyScalar(10);          // builder/preview.py SUN_DIRECTION
    this.scene.add(hemi, sun);
    this.ground = new THREE.Mesh(new THREE.PlaneGeometry(12, 12).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 1 }));
    this.grid = new THREE.GridHelper(12, 48);
    (this.grid.material as THREE.LineBasicMaterial).transparent = true;
    (this.grid.material as THREE.LineBasicMaterial).opacity = 0.35;
    this.grid.position.y = 0.001;
    this.scene.add(this.ground, this.grid);
    this.applyTheme();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.intersectionObserver = new IntersectionObserver(([entry]) => {
      this.visible = entry.isIntersecting;
      if (this.visible) this.needsRender = true;
    });
    this.intersectionObserver.observe(container);
    this.resize();
    this.loop();
  }

  // ------------------------------------------------------------------ loading
  async setModels(leftUrl: string | null, rightUrl: string | null): Promise<void> {
    if (this.disposed) return;
    const token = ++this.token;
    const results = await Promise.allSettled([leftUrl ? loader.loadAsync(leftUrl) : null, rightUrl ? loader.loadAsync(rightUrl) : null]);
    const failure = results.find((result) => result.status === "rejected");
    if (token !== this.token || this.disposed || failure) {
      for (const result of results) if (result.status === "fulfilled" && result.value) disposeModelResources(result.value.scene);
      if (token !== this.token || this.disposed) return;
      throw failure!.reason;
    }
    const [l, r] = results.map((result) => result.status === "fulfilled" ? result.value : null);
    this.clear();
    this.left = l ? this.adopt(l.scene) : null;
    this.right = r ? this.adopt(r.scene) : null;
    this.refresh();
    this.preset("front");
  }

  private adopt(root: THREE.Object3D): Side {
    const meshes: THREE.Mesh[] = [];
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.userData.orig = m.material;
        (Array.isArray(m.material) ? m.material : [m.material]).forEach((mat) => {
          (mat as THREE.MeshStandardMaterial).flatShading = true;
          mat.needsUpdate = true;
        });
        meshes.push(m);
      }
    });
    this.scene.add(root);
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    let helper: THREE.SkeletonHelper | null = null;
    if (root.getObjectByProperty("isBone", true)) {
      helper = new THREE.SkeletonHelper(root);
      (helper.material as THREE.LineBasicMaterial).depthTest = false;
      helper.renderOrder = 30;
      this.scene.add(helper);
    }
    return { root, meshes, helper, width: box.isEmpty() ? 1 : box.max.x - box.min.x };
  }

  private clear(): void {
    this.dropOverlays();
    const made = new Set(this.made);
    this.made.forEach((material) => material.dispose());
    this.made = [];
    for (const side of [this.left, this.right]) {
      if (!side) continue;
      this.scene.remove(side.root);
      if (side.helper) {
        this.scene.remove(side.helper);
        side.helper.dispose();
      }
      disposeModelResources(side.root, "orig", made);
    }
    this.left = this.right = null;
  }

  // ------------------------------------------------------------------ modes
  setDisplay(mode: DisplayMode): void { this.display = mode; this.refresh(); }
  setCompare(mode: CompareMode): void { this.compare = mode; this.refresh(); this.preset("front"); }
  setOpacity(value: number): void { this.opacity = value; this.refresh(); }
  setWeightBone(name: string): void { this.weightBone = name; this.refresh(); }

  /** Re-apply layout and materials after any mode change. */
  refresh(): void {
    if (this.disposed) return;
    this.needsRender = true;
    this.dropOverlays();
    const stale = this.made;
    this.made = [];
    const { left, right } = this;
    const pair = this.compare !== "single" && left && right;
    if (right) {
      right.root.visible = this.compare !== "single";
      if (right.helper) right.helper.visible = false;          // style() turns it back on when shown
    }
    if (left) left.root.position.x = 0;
    if (right) right.root.position.x = 0;
    if (pair && this.compare === "side") {
      const gap = Math.max(left.width, right.width) * 0.5 + 0.45;
      left.root.position.x = -gap;
      right.root.position.x = gap;
    }
    for (const s of [left, right]) s?.root.updateMatrixWorld(true);
    if (left) this.style(left, "left", pair ? this.compare : "single");
    if (right && pair) this.style(right, "right", this.compare);
    stale.forEach((m) => m.dispose());
  }

  private own<T extends THREE.Material>(mat: T): T {
    this.made.push(mat);
    return mat;
  }

  private cloneMaterials(original: THREE.Material | THREE.Material[], change: (material: THREE.Material) => void): THREE.Material | THREE.Material[] {
    const clone = (material: THREE.Material) => {
      const copy = this.own(material.clone());
      change(copy);
      return copy;
    };
    return Array.isArray(original) ? original.map(clone) : clone(original);
  }

  private style(side: Side, which: "left" | "right", compare: CompareMode | "single"): void {
    if (side.helper) side.helper.visible = this.display === "armature" && (compare === "single" || compare === "side");
    for (const mesh of side.meshes) {
      const orig = mesh.userData.orig as THREE.Material | THREE.Material[];
      mesh.renderOrder = 0;
      if (compare === "silhouette") {
        mesh.material = this.own(new THREE.MeshBasicMaterial({ color: which === "left" ? LEFT_COLOR : RIGHT_COLOR, transparent: true,
          opacity: which === "left" ? 0.65 : this.opacity, depthWrite: false, side: THREE.DoubleSide }));
        mesh.renderOrder = which === "left" ? 1 : 2;
        continue;
      }
      if (compare === "wire") {
        mesh.material = this.own(new THREE.MeshBasicMaterial({ color: which === "left" ? LEFT_COLOR : RIGHT_COLOR, wireframe: true,
          transparent: which === "right", opacity: which === "right" ? Math.max(this.opacity, 0.35) : 1 }));
        continue;
      }
      if (compare === "overlay" && which === "right") {
        mesh.material = this.cloneMaterials(orig, (mat) => {
          mat.transparent = true;
          mat.opacity = this.opacity;
          mat.depthWrite = false;
        });
        mesh.renderOrder = 5;
        continue;
      }
      switch (this.display) {
        case "solid":
          mesh.material = orig;
          break;
        case "wire":
          mesh.material = this.own(new THREE.MeshBasicMaterial({ color: new THREE.Color(cssVar("--text", "#222")), wireframe: true }));
          break;
        case "solidwire": {
          mesh.material = this.cloneMaterials(orig, (solid) => {
            solid.polygonOffset = true;
            solid.polygonOffsetFactor = 1;
            solid.polygonOffsetUnits = 1;
          });
          this.addWire(mesh);
          break;
        }
        case "normals":
          mesh.material = this.own(new THREE.MeshNormalMaterial({ flatShading: true }));
          break;
        case "armature": {
          mesh.material = this.cloneMaterials(orig, (ghost) => {
            ghost.transparent = true;
            ghost.opacity = 0.35;
            ghost.depthWrite = false;
          });
          break;
        }
        case "weights":
          mesh.material = this.weightMaterial(mesh);
          break;
      }
    }
  }

  private addWire(mesh: THREE.Mesh): void {
    const mat = this.own(new THREE.MeshBasicMaterial({ color: 0x111111, wireframe: true, transparent: true, opacity: 0.8 }));
    const skinned = mesh as THREE.SkinnedMesh;
    let wire: THREE.Mesh;
    if (skinned.isSkinnedMesh) {
      const s = new THREE.SkinnedMesh(mesh.geometry, mat);
      s.bind(skinned.skeleton, skinned.bindMatrix);
      wire = s;
    } else {
      wire = new THREE.Mesh(mesh.geometry, mat);
    }
    wire.userData.overlay = true;
    mesh.add(wire);
    this.overlays.push(wire);
  }

  /** Heat map of the selected bone's weight; meshes without a skin show their vertex colours (regions). */
  private weightMaterial(mesh: THREE.Mesh): THREE.Material {
    const geo = mesh.geometry as THREE.BufferGeometry;
    const skinned = mesh as THREE.SkinnedMesh;
    if (!skinned.isSkinnedMesh || !geo.getAttribute("skinIndex")) {
      return geo.getAttribute("color")
        ? this.own(new THREE.MeshBasicMaterial({ vertexColors: true }))
        : this.own(new THREE.MeshBasicMaterial({ color: 0x777777 }));
    }
    const bone = skinned.skeleton.bones.findIndex((b) => b.name === this.weightBone || b.name === this.weightBone.replace(".", "_"));
    const idx = geo.getAttribute("skinIndex");
    const wts = geo.getAttribute("skinWeight");
    const colors = new Float32Array(idx.count * 3);
    for (let i = 0; i < idx.count; i++) {
      let w = 0;
      for (let k = 0; k < 4; k++) if (idx.getComponent(i, k) === bone) w += wts.getComponent(i, k);
      const c = bone < 0 ? new THREE.Color(0x335) : heat(w);
      colors.set([c.r, c.g, c.b], i * 3);
    }
    geo.setAttribute("labWeight", new THREE.BufferAttribute(colors, 3));
    const mat = this.own(new THREE.MeshBasicMaterial({ vertexColors: true }));
    mat.onBeforeCompile = (shader) => {                     // read labWeight instead of the palette colours
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nattribute vec3 labWeight;")
        .replace("#include <color_vertex>", "#include <color_vertex>\nvColor = vec4(labWeight, 1.0);");
    };
    mat.customProgramCacheKey = () => "labWeight";
    return mat;
  }

  private dropOverlays(): void {
    for (const o of this.overlays) o.parent?.remove(o);
    this.overlays = [];
  }

  // ------------------------------------------------------------------ meshes
  meshes(): LabMeshInfo[] {
    const out: LabMeshInfo[] = [];
    for (const [sideName, side] of [["left", this.left], ["right", this.right]] as const) {
      if (!side) continue;
      for (const m of side.meshes) {
        const geo = m.geometry as THREE.BufferGeometry;
        const index = geo.index;
        const tris = index ? index.count / 3 : geo.attributes.position.count / 3;
        const edges = new Set<string>();
        const pos = geo.attributes.position;
        const key = (i: number) => `${pos.getX(i).toFixed(5)},${pos.getY(i).toFixed(5)},${pos.getZ(i).toFixed(5)}`;
        if (index) {
          for (let t = 0; t < index.count; t += 3) {
            const a = key(index.getX(t)), b = key(index.getX(t + 1)), c = key(index.getX(t + 2));
            for (const [p, q] of [[a, b], [b, c], [c, a]]) edges.add(p < q ? `${p}|${q}` : `${q}|${p}`);
          }
        }
        const verts = new Set<string>();
        for (let i = 0; i < pos.count; i++) verts.add(key(i));
        geo.computeBoundingBox();
        const size = geo.boundingBox!.getSize(new THREE.Vector3());
        const skinned = (m as THREE.SkinnedMesh).isSkinnedMesh;
        let groups = 0;
        let maxInfluences = 0;
        const wts = geo.getAttribute("skinWeight");
        const idx = geo.getAttribute("skinIndex");
        if (skinned && wts && idx) {
          const used = new Set<number>();
          for (let i = 0; i < wts.count; i++) {
            let n = 0;
            for (let k = 0; k < 4; k++) {
              if (wts.getComponent(i, k) > 1e-3) {
                n++;
                used.add(idx.getComponent(i, k));
              }
            }
            maxInfluences = Math.max(maxInfluences, n);
          }
          groups = used.size;
        }
        const mats = Array.isArray(m.userData.orig) ? m.userData.orig : [m.userData.orig];
        out.push({
          name: m.name, side: sideName, verts: verts.size, edges: edges.size, tris, visible: m.visible,
          size: [size.x, size.y, size.z], materials: mats.map((x: THREE.Material) => x.name || "—"),
          skinned, bones: skinned ? (m as THREE.SkinnedMesh).skeleton.bones.length : 0, groups, maxInfluences,
          colors: !!geo.getAttribute("color"),
        });
      }
    }
    return out;
  }

  bones(): string[] {
    const m = [...(this.left?.meshes ?? []), ...(this.right?.meshes ?? [])].find((x) => (x as THREE.SkinnedMesh).isSkinnedMesh);
    return m ? (m as THREE.SkinnedMesh).skeleton.bones.map((b) => b.name) : [];
  }

  private find(side: "left" | "right", name: string): THREE.Mesh | undefined {
    return (side === "left" ? this.left : this.right)?.meshes.find((m) => m.name === name);
  }

  isolate(side: "left" | "right", name: string): void {
    this.needsRender = true;
    for (const s of [this.left, this.right]) s?.meshes.forEach((m) => { m.visible = false; });
    const m = this.find(side, name);
    if (m) m.visible = true;
  }

  toggle(side: "left" | "right", name: string): void {
    this.needsRender = true;
    const m = this.find(side, name);
    if (m) m.visible = !m.visible;
  }

  showAll(): void {
    this.needsRender = true;
    for (const s of [this.left, this.right]) s?.meshes.forEach((m) => { m.visible = true; });
  }

  frameMesh(side: "left" | "right", name: string): void {
    const m = this.find(side, name);
    if (!m) return;
    const box = new THREE.Box3().setFromObject(m);
    this.fit(box, this.currentDirection());
  }

  // ------------------------------------------------------------------ camera
  private currentDirection(): THREE.Vector3 {
    return this.camera.position.clone().sub(this.controls.target).normalize();
  }

  preset(name: LabPreset): void {
    const box = new THREE.Box3();
    for (const s of [this.left, this.compare === "single" ? null : this.right]) if (s) box.expandByObject(s.root);
    if (box.isEmpty()) box.set(new THREE.Vector3(-0.5, 0, -0.5), new THREE.Vector3(0.5, 2, 0.5));
    this.fit(box, DIRECTIONS[name]);
  }

  private fit(box: THREE.Box3, dir: THREE.Vector3): void {
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const aspect = Math.max(this.el.clientWidth, 1) / Math.max(this.el.clientHeight, 1);
    this.viewHeight = Math.max(0.1, size.y, Math.max(size.x, size.z) / aspect) * 1.15;
    this.camera.position.copy(center).addScaledVector(dir, 10);
    this.controls.target.copy(center);
    this.camera.zoom = 1;
    this.resize();
    this.controls.update();
  }

  // ------------------------------------------------------------------ loop
  applyTheme(): void {
    this.needsRender = true;
    this.scene.background = new THREE.Color(cssVar("--viewer-bg", "#20242a"));
    (this.ground.material as THREE.MeshStandardMaterial).color.set(cssVar("--viewer-ground", "#3a3f46"));
  }

  private resize(): void {
    if (this.disposed) return;
    this.needsRender = true;
    const w = Math.max(this.el.clientWidth, 1);
    const h = Math.max(this.el.clientHeight, 1);
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = `${w}px`;
    this.renderer.domElement.style.height = `${h}px`;
    const half = this.viewHeight / 2;
    this.camera.left = -half * (w / h);
    this.camera.right = half * (w / h);
    this.camera.top = half;
    this.camera.bottom = -half;
    this.camera.updateProjectionMatrix();
  }

  private loop = (): void => {
    if (this.disposed) return;
    this.frameId = requestAnimationFrame(this.loop);
    if (document.hidden || !this.visible || this.contextLost || !this.el.clientWidth || !this.el.clientHeight) return;
    this.controls.update();
    if (!this.needsRender) return;
    this.needsRender = false;
    this.renderer.render(this.scene, this.camera);
  };

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.token++;
    cancelAnimationFrame(this.frameId);
    this.resizeObserver.disconnect();
    this.intersectionObserver.disconnect();
    this.clear();
    disposeModelResources(this.ground);
    disposeModelResources(this.grid);
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
  }
}
