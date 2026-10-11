// three.js viewer for built GLB models.

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { CSS2DObject, CSS2DRenderer } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";
import {
  EDGE_SHADER,
  createHullMaterial,
  createToonMaterial,
  disposeModelResources,
  ensureOutlineNormals,
  updateToonMaterial,
  type ToonParams,
} from "./toon";

export type ViewPreset = "iso" | "front" | "side" | "top" | "34";

export interface ModelMeta {
  gridSize?: [number, number, number] | null;
  voxelSize?: number;
  preset?: ViewPreset;          // initial camera (characters: "34")
  clip?: string;                // preferred first clip (characters: "idle")
  animate?: boolean;            // false shows a workbench at its initial pose
}

export interface LayoutModel {
  url: string;
  label: string;
  ref: string;
  position: [number, number, number];
}

export interface ViewerInfo {
  tris: number;
  verts: number;
  size: THREE.Vector3;
  voxels: THREE.Vector3;
  clips: string[];
  sockets: string[];
  aim?: { axis: "yaw" | "pitch"; min: number; max: number; value: number }[];
}

export interface ViewerOptions {
  wireframe: boolean;
  grid: boolean;
  sockets: boolean;
  collision: boolean;
  autoRotate: boolean;
  skeleton: boolean;
}

export interface EditableSlot {
  name: string;
  host: string | null;
}

// glTF convention used by the registry: +Y up, façade faces +Z.
const PRESET_DIRECTIONS: Record<ViewPreset, THREE.Vector3> = {
  iso: new THREE.Vector3(1, 1, 1).normalize(),
  front: new THREE.Vector3(0, 0, 1),
  side: new THREE.Vector3(1, 0, 0),
  top: new THREE.Vector3(0, 1, 0.0001).normalize(),
  "34": new THREE.Vector3(0.62, 0.34, 1).normalize(),     // 3/4 from front-right, close to a game camera
};

const loader = new GLTFLoader();
// Canonical key light (toward the light, glTF axes) — same as builder/preview.py SUN_DIRECTION.
const SUN_DIRECTION = new THREE.Vector3(-0.45, 0.7, 0.55).normalize();

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}


export class Viewer {
  readonly el: HTMLElement;
  onCameraChange: (() => void) | null = null;
  onSlotPick: ((slot: string) => void) | null = null;
  onSlotMove: ((slot: string, delta: [number, number, number]) => void) | null = null;
  /** The GPU dropped the WebGL context (memory pressure, driver reset); restored → reload. */
  onContextLost: (() => void) | null = null;
  onContextRestored: (() => void) | null = null;
  onAnimationFinished: (() => void) | null = null;

  private renderer: THREE.WebGLRenderer;
  private labels: CSS2DRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(35, 1, 0.01, 500);
  private controls: OrbitControls;
  private timer = new THREE.Timer();
  private hemi = new THREE.HemisphereLight(0xffffff, 0x6b6660, 1.6);
  private sun = new THREE.DirectionalLight(0xffffff, 2.2);
  private ground: THREE.Mesh;
  private floorGrid: THREE.GridHelper;
  private environmentTarget: THREE.WebGLRenderTarget | null = null;

  private model: THREE.Object3D | null = null;
  private visualMeshes: THREE.Mesh[] = [];
  private collisionMeshes: THREE.Mesh[] = [];
  private socketHelpers: THREE.Object3D[] = [];
  private slotRoots = new Map<string, THREE.Object3D>();
  private slotGroups = new Map<string, THREE.Group>();
  private slotBasePositions = new Map<string, THREE.Vector3>();
  private slotHosts = new Map<string, string | null>();
  private slotDeltas: Record<string, [number, number, number]> = {};
  private assetRoot: THREE.Object3D | null = null;
  private selectedSlot: string | null = null;
  private transformControls: TransformControls | null = null;
  private translationSnap: number | null = 0.25;
  private dragStartWorld: THREE.Vector3 | null = null;
  private suppressNextPick = false;
  private selectionBox: THREE.BoxHelper | null = null;
  private pointerStart: THREE.Vector2 | null = null;
  private raycaster = new THREE.Raycaster();
  private envelope: THREE.Group | null = null;
  // one mixer per loaded model; a cast plays the same clip name on every member
  private mixers: { mixer: THREE.AnimationMixer; clips: THREE.AnimationClip[]; action: THREE.AnimationAction | null }[] = [];
  private clips: THREE.AnimationClip[] = [];
  private clipLoops = new Map<string, boolean>();
  private skeletonHelper: THREE.SkeletonHelper | null = null;
  private playing = false;
  private aimJoints: { object: THREE.Object3D; base: THREE.Quaternion; axis: "yaw" | "pitch";
    min: number; max: number; value: number; angle: number; sign: number }[] = [];

  private bounds = new THREE.Box3();
  private radius = 1;
  private initialPreset: ViewPreset = "iso";
  private syncing = false;
  private frame = 0;
  private resizeObserver: ResizeObserver;
  private intersectionObserver: IntersectionObserver;
  private visible = true;
  private needsRender = true;
  private contextLost = false;
  private disposed = false;
  private loadToken = 0;

  // materials: null = PBR as exported; otherwise the procedural toon
  private toonParams: ToonParams | null = null;
  private toonMaterial: THREE.ShaderMaterial | null = null;
  private toonByColor = new Map<string, THREE.ShaderMaterial>();   // meshes without vertex colors
  private hullMaterial: THREE.ShaderMaterial | null = null;
  private hulls: THREE.Mesh[] = [];
  private composer: EffectComposer | null = null;
  private edgePass: ShaderPass | null = null;
  private normalTarget: THREE.WebGLRenderTarget | null = null;
  private normalMaterial = new THREE.MeshNormalMaterial({ flatShading: true });

  options: ViewerOptions = { wireframe: false, grid: false, sockets: false, collision: false, autoRotate: false, skeleton: false };

  constructor(container: HTMLElement) {
    this.el = container;
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.domElement.classList.add("viewer-canvas");
    container.appendChild(this.renderer.domElement);
    this.renderer.domElement.addEventListener("webglcontextlost", (ev) => {
      ev.preventDefault();                                   // lets the browser restore the context
      this.contextLost = true;
      if (!this.disposed) this.onContextLost?.();
    });
    this.renderer.domElement.addEventListener("webglcontextrestored", () => {
      if (this.disposed) return;
      this.contextLost = false;
      this.setupEnvironment();
      this.needsRender = true;
      this.onContextRestored?.();
    });
    this.renderer.domElement.addEventListener("pointerdown", (ev) => {
      this.suppressNextPick = false;
      this.pointerStart = new THREE.Vector2(ev.clientX, ev.clientY);
    });
    this.renderer.domElement.addEventListener("pointerup", (ev) => {
      const start = this.pointerStart;
      this.pointerStart = null;
      if (!start || !this.onSlotPick || this.suppressNextPick) return;
      const distance = start.distanceTo(new THREE.Vector2(ev.clientX, ev.clientY));
      if (distance > 5) return;
      this.pickSlot(ev);
    });

    this.labels = new CSS2DRenderer();
    this.labels.domElement.classList.add("viewer-labels");
    container.appendChild(this.labels.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.controls.autoRotateSpeed = 1.6;
    this.controls.addEventListener("change", () => {
      this.needsRender = true;
      if (!this.syncing) this.onCameraChange?.();
    });
    this.timer.connect(document);

    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.bias = -0.0005;
    this.sun.shadow.normalBias = 0.02;
    this.scene.add(this.hemi, this.sun, this.sun.target);
    this.setupEnvironment();

    this.ground = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 1 }),
    );
    this.ground.receiveShadow = true;
    this.floorGrid = new THREE.GridHelper(1, 1);
    this.scene.add(this.ground, this.floorGrid);

    this.applyTheme();
    this.setGroundSize(4);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.intersectionObserver = new IntersectionObserver(([entry]) => {
      this.visible = entry.isIntersecting;
      if (this.visible) this.needsRender = true;
    });
    this.intersectionObserver.observe(container);
    this.resize();
    this.animate();
  }

  // ------------------------------------------------------------------ loading
  private setupEnvironment(): void {
    const room = new RoomEnvironment();
    const generator = new THREE.PMREMGenerator(this.renderer);
    try {
      const target = generator.fromScene(room, 0.04);
      this.environmentTarget?.dispose();
      this.environmentTarget = target;
      this.scene.environment = target.texture;
      this.scene.environmentIntensity = 0.65;
    } finally {
      // RoomEnvironment.dispose() handles shared geometry/materials; its
      // InstancedMesh also owns instance buffers registered by the renderer.
      room.traverse((object) => {
        if (object instanceof THREE.InstancedMesh) object.dispose();
      });
      room.dispose();
      generator.dispose();
    }
  }

  async load(url: string, meta: ModelMeta = {}): Promise<ViewerInfo> {
    return this.loadMany([url], meta);
  }

  /** Components on a shared workbench; positions match the exported Blender sheet. */
  async loadLayout(items: LayoutModel[], meta: ModelMeta = {}): Promise<ViewerInfo> {
    return this.loadMany(items.map((item) => item.url), { animate: false, ...meta }, 0, items);
  }

  /** Several models side by side along X, `spacing` metres apart (the character cast). */
  async loadMany(urls: string[], meta: ModelMeta = {}, spacing = 1.35,
                 layout?: LayoutModel[]): Promise<ViewerInfo> {
    if (this.disposed) throw new Error("superseded");
    const token = ++this.loadToken;
    const results = await Promise.allSettled(urls.map((u) => loader.loadAsync(u)));
    const gltfs = results.flatMap((result) => result.status === "fulfilled" ? [result.value] : []);
    const failure = results.find((result) => result.status === "rejected");
    if (token !== this.loadToken || this.disposed || failure) {
      for (const gltf of gltfs) disposeModelResources(gltf.scene);
      if (token !== this.loadToken || this.disposed) throw new Error("superseded");
      throw failure!.reason;
    }
    this.clearModel();

    let model: THREE.Object3D;
    const layoutRoots: { node: THREE.Group; item: LayoutModel }[] = [];
    if (gltfs.length === 1 && !layout) {
      model = gltfs[0].scene;
    } else {
      model = new THREE.Group();
      gltfs.forEach((g, i) => {
        if (layout) {
          const node = new THREE.Group();
          node.name = `sheet_${layout[i].ref}`;
          node.position.fromArray(layout[i].position);
          node.userData.sheet_ref = layout[i].ref;
          node.add(g.scene);
          model.add(node);
          layoutRoots.push({ node, item: layout[i] });
        } else {
          g.scene.position.x = (i - (gltfs.length - 1) / 2) * spacing;
          model.add(g.scene);
        }
      });
    }
    this.model = model;
    const voxelSize = meta.voxelSize ?? 0.25;
    model.traverse((obj) => {
      if ((obj as THREE.Mesh).isMesh) {
        const mesh = obj as THREE.Mesh;
        if (mesh.name.endsWith("-colonly")) {
          mesh.userData.pbr = mesh.material;
          mesh.material = new THREE.MeshBasicMaterial({
            color: 0xff7a1a, transparent: true, opacity: 0.28, depthWrite: false, side: THREE.DoubleSide,
          });
          mesh.renderOrder = 10;
          this.collisionMeshes.push(mesh);
        } else {
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          for (const m of materials) (m as THREE.MeshStandardMaterial).flatShading = true;
          this.visualMeshes.push(mesh);
        }
      } else if (obj.name.startsWith("socket_")) {
        this.addSocketHelper(obj);
      }
    });
    this.scene.add(model);
    model.updateMatrixWorld(true);

    this.aimJoints = [];
    model.traverse((object) => {
      const data = object.userData;
      if ((data.aim_axis === "yaw" || data.aim_axis === "pitch") &&
        [data.aim_min, data.aim_max, data.aim_default, data.aim_sign].every((v) => typeof v === "number" && Number.isFinite(v)) &&
        data.aim_min <= data.aim_default && data.aim_default <= data.aim_max) {
        this.aimJoints.push({ object, base: object.quaternion.clone(), axis: data.aim_axis,
          min: data.aim_min, max: data.aim_max, value: data.aim_default, angle: data.aim_default, sign: data.aim_sign });
      }
    });

    // Per-geometry bounds: Box3.expandByObject would also include socket helpers (children).
    this.bounds.makeEmpty();
    for (const mesh of this.visualMeshes) {
      mesh.geometry.computeBoundingBox();
      if (mesh.geometry.boundingBox) this.bounds.union(mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld));
    }
    if (this.bounds.isEmpty()) this.bounds.set(new THREE.Vector3(-0.5, 0, -0.5), new THREE.Vector3(0.5, 1, 0.5));
    const size = this.bounds.getSize(new THREE.Vector3());
    const aimingRadius = layout ? null : this.fitAimingBounds();
    this.radius = Math.max(aimingRadius ?? size.length() / 2, 0.25);
    for (const helper of this.socketHelpers) helper.scale.setScalar(Math.max(0.12, this.radius * 0.18));

    if (meta.gridSize) this.buildEnvelope(meta.gridSize, voxelSize);
    this.setGroundSize(Math.max(4, Math.ceil(this.radius * 6)));
    this.fitShadow();

    for (const { node, item } of layoutRoots) {
      const box = new THREE.Box3();
      for (const mesh of this.visualMeshes) {
        if (node.getObjectById(mesh.id) && mesh.geometry.boundingBox) {
          box.union(mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld));
        }
      }
      if (box.isEmpty()) continue;
      const text = document.createElement("div");
      text.className = "viewer-sheet-label";
      text.textContent = item.label;
      text.title = item.ref;
      const label = new CSS2DObject(text);
      label.position.set((box.min.x + box.max.x) / 2, 0.015, box.max.z + voxelSize);
      model.add(label);
    }

    this.clipLoops.clear();
    model.traverse((object) => {
      if (typeof object.userData.animation_contract !== "string") return;
      try {
        const contract: unknown = JSON.parse(object.userData.animation_contract);
        if (contract && typeof contract === "object") for (const [name, spec] of Object.entries(contract)) {
          if (spec && typeof spec === "object" && typeof spec.loop === "boolean") this.clipLoops.set(name, spec.loop);
        }
      } catch { /* A malformed optional contract leaves the standard looping behaviour. */ }
    });
    this.mixers = gltfs.filter((g) => g.animations.length)
      .map((g) => {
        const mixer = new THREE.AnimationMixer(g.scene);
        mixer.addEventListener("finished", () => {
          if (this.mixers.every((member) => !member.action?.isRunning())) {
            this.playing = false;
            this.needsRender = true;
            this.onAnimationFinished?.();
          }
        });
        return { mixer, clips: g.animations, action: null };
      });
    const names = [...new Set(gltfs.flatMap((g) => g.animations.map((c) => c.name)))];
    if (names.includes("idle")) { names.splice(names.indexOf("idle"), 1); names.unshift("idle"); }
    this.clips = names.map((n) => gltfs.flatMap((g) => g.animations).find((c) => c.name === n)!);
    if (this.clips.length) {
      this.play(meta.clip && names.includes(meta.clip) ? meta.clip : this.clips[0].name);
      if (meta.animate === false) {
        for (const member of this.mixers) member.mixer.update(0);
        this.togglePlay();
      }
    }
    if (model.getObjectByProperty("isBone", true)) {
      this.skeletonHelper = new THREE.SkeletonHelper(model);
      (this.skeletonHelper.material as THREE.LineBasicMaterial).depthTest = false;
      this.skeletonHelper.renderOrder = 25;
      this.scene.add(this.skeletonHelper);
    }
    this.applyMaterial();
    this.applyOptions();
    this.initialPreset = meta.preset ?? "iso";
    this.preset(this.initialPreset);

    let tris = 0;
    let verts = 0;
    for (const mesh of this.visualMeshes) {
      const geo = mesh.geometry as THREE.BufferGeometry;
      const count = geo.index ? geo.index.count : geo.attributes.position.count;
      tris += count / 3;
      verts += geo.attributes.position.count;
    }
    return {
      tris, verts, size,
      voxels: size.clone().divideScalar(voxelSize),
      clips: this.clips.map((c) => c.name),
      sockets: this.socketHelpers.map((s) => s.userData.socket as string),
      aim: this.aimJoints.map(({ axis, min, max, value }) => ({ axis, min, max, value })),
    };
  }

  /** Remove the current model (e.g. while the selected variant has no build yet). */
  clear(): void {
    this.loadToken++;
    this.clearModel();
  }

  private clearModel(): void {
    this.needsRender = true;
    this.aimJoints = [];
    this.transformControls?.detach();
    this.controls.enabled = true;
    this.dragStartWorld = null;
    this.selectedSlot = null;
    this.assetRoot = null;
    this.clearSelectionBox();
    this.slotRoots.clear();
    this.slotGroups.clear();
    this.slotBasePositions.clear();
    this.slotHosts.clear();
    this.slotDeltas = {};
    if (this.model) {
      this.scene.remove(this.model);
      const shared = new Set<THREE.Material>([...this.toonByColor.values()]);
      if (this.toonMaterial) shared.add(this.toonMaterial);
      if (this.hullMaterial) shared.add(this.hullMaterial);
      disposeModelResources(this.model, "pbr", shared);
      this.model.traverse((obj) => {
        if (obj instanceof CSS2DObject) obj.element.remove();
      });
    }
    if (this.envelope) {
      this.scene.remove(this.envelope);
      disposeModelResources(this.envelope);
      this.envelope = null;
    }
    for (const m of this.mixers) {
      m.mixer.stopAllAction();
      m.mixer.uncacheRoot(m.mixer.getRoot());
    }
    this.mixers = [];
    if (this.skeletonHelper) {
      this.scene.remove(this.skeletonHelper);
      this.skeletonHelper.dispose();
      this.skeletonHelper = null;
    }
    this.playing = false;
    this.clips = [];
    this.clipLoops.clear();
    this.model = null;
    this.visualMeshes = [];
    this.collisionMeshes = [];
    this.socketHelpers = [];
    this.hulls = [];
  }

  /** Each assembled component is one root child in the exported asset. */
  configureSlotEditing(slots: EditableSlot[]): string[] {
    this.transformControls?.detach();
    this.dragStartWorld = null;
    this.selectedSlot = null;
    this.controls.enabled = true;
    this.clearSelectionBox();
    this.slotRoots.clear();
    this.slotGroups.clear();
    this.slotBasePositions.clear();
    this.slotDeltas = {};
    this.slotHosts = new Map(slots.map((slot) => [slot.name, slot.host]));
    this.assetRoot = null;
    this.model?.traverse((obj) => {
      if (!this.assetRoot && obj.userData.kind === "asset") this.assetRoot = obj;
    });
    if (!this.assetRoot) return [];
    const root: THREE.Object3D = this.assetRoot;
    const names = slots.map((slot) => slot.name).sort((a, b) => b.length - a.length);
    for (const child of [...root.children]) {
      const name = names.find((slot) => child.name.startsWith(`${slot}_`));
      if (!name || this.slotRoots.has(name)) continue;
      // Put the handle at the component's exported pivot. The compensating inner
      // group leaves the original node and all of its animation tracks untouched.
      const pivot = child.position.clone();
      const wrapper = new THREE.Group();
      wrapper.name = `editor_offset_${name}`;
      wrapper.position.copy(pivot);
      const content = new THREE.Group();
      content.position.copy(pivot).negate();
      root.add(wrapper);
      wrapper.add(content);
      content.add(child);
      this.slotRoots.set(name, child);
      this.slotGroups.set(name, wrapper);
      this.slotBasePositions.set(name, pivot);
    }
    this.ensureTransformControls();
    return [...this.slotGroups.keys()];
  }

  private ensureTransformControls(): void {
    if (this.transformControls) return;
    const gizmo = new TransformControls(this.camera, this.renderer.domElement);
    gizmo.addEventListener("change", () => { this.needsRender = true; });
    gizmo.setMode("translate");
    gizmo.setSpace("world");
    // Built-in absolute snapping shifts off-grid socket pivots on the first drag.
    // Snap the movement relative to its starting position in onGizmoMove instead.
    gizmo.setTranslationSnap(null);
    gizmo.setSize(0.85);
    gizmo.addEventListener("mouseDown", () => {
      this.suppressNextPick = true;
      const group = this.selectedSlot ? this.slotGroups.get(this.selectedSlot) : null;
      this.dragStartWorld = group ? group.getWorldPosition(new THREE.Vector3()) : null;
    });
    gizmo.addEventListener("mouseUp", () => { this.dragStartWorld = null; });
    gizmo.addEventListener("dragging-changed", (event) => {
      this.controls.enabled = !event.value;
    });
    gizmo.addEventListener("objectChange", () => this.onGizmoMove());
    this.transformControls = gizmo;
    this.scene.add(gizmo.getHelper());
  }

  /** null disables snapping; positive values snap translation relative to drag start. */
  setTranslationSnap(step: number | null): void {
    this.translationSnap = step && Number.isFinite(step) && step > 0 ? step : null;
  }

  private slotShift(name: string | null): THREE.Vector3 {
    const shift = new THREE.Vector3();
    const seen = new Set<string>();
    let current = name;
    while (current && !seen.has(current)) {
      seen.add(current);
      const delta = this.slotDeltas[current];
      if (delta) shift.add(new THREE.Vector3(...delta));
      current = this.slotHosts.get(current) ?? null;
    }
    return shift;
  }

  /** Deltas are glTF world-axis metres relative to the loaded parent build. */
  applySlotDeltas(deltas: Record<string, [number, number, number]>): void {
    this.needsRender = true;
    this.slotDeltas = deltas;
    if (!this.assetRoot) return;
    this.assetRoot.updateWorldMatrix(true, false);
    const inverseBasis = new THREE.Matrix3().setFromMatrix4(this.assetRoot.matrixWorld).invert();
    for (const [name, group] of this.slotGroups) {
      const pivot = this.slotBasePositions.get(name)!;
      group.position.copy(pivot).add(this.slotShift(name).applyMatrix3(inverseBasis));
    }
    this.model?.updateMatrixWorld(true);
    this.selectionBox?.update();
  }

  private onGizmoMove(): void {
    const name = this.selectedSlot;
    if (!name || !this.assetRoot || !this.dragStartWorld) return;
    const group = this.slotGroups.get(name);
    const pivot = this.slotBasePositions.get(name);
    if (!group || !pivot || !group.parent) return;
    group.updateWorldMatrix(true, false);
    const world = group.getWorldPosition(new THREE.Vector3());
    if (this.translationSnap) {
      const movement = world.sub(this.dragStartWorld);
      for (const axis of ["x", "y", "z"] as const) {
        movement[axis] = Math.round(movement[axis] / this.translationSnap) * this.translationSnap;
      }
      const snappedWorld = this.dragStartWorld.clone().add(movement);
      group.position.copy(group.parent.worldToLocal(snappedWorld));
    }
    this.assetRoot.updateWorldMatrix(true, false);
    const basis = new THREE.Matrix3().setFromMatrix4(this.assetRoot.matrixWorld);
    const totalShift = group.position.clone().sub(pivot).applyMatrix3(basis);
    const ownShift = totalShift.sub(this.slotShift(this.slotHosts.get(name) ?? null));
    this.selectionBox?.update();
    this.onSlotMove?.(name, [ownShift.x, ownShift.y, ownShift.z]);
  }

  selectSlot(name: string | null): void {
    this.needsRender = true;
    this.clearSelectionBox();
    this.selectedSlot = name;
    const group = name ? this.slotGroups.get(name) : null;
    if (!group) {
      this.transformControls?.detach();
      return;
    }
    this.transformControls?.attach(group);
    this.selectionBox = new THREE.BoxHelper(group, cssVar("--accent", "#d9822b"));
    this.selectionBox.renderOrder = 30;
    const material = this.selectionBox.material as THREE.LineBasicMaterial;
    material.depthTest = false;
    material.transparent = true;
    this.scene.add(this.selectionBox);
  }

  private clearSelectionBox(): void {
    if (!this.selectionBox) return;
    this.scene.remove(this.selectionBox);
    this.selectionBox.geometry.dispose();
    (this.selectionBox.material as THREE.Material).dispose();
    this.selectionBox = null;
  }

  private pickSlot(ev: PointerEvent): void {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const point = new THREE.Vector2(
      ((ev.clientX - rect.left) / rect.width) * 2 - 1,
      -((ev.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(point, this.camera);
    for (const hit of this.raycaster.intersectObjects(this.visualMeshes, false)) {
      let obj: THREE.Object3D | null = hit.object;
      while (obj) {
        for (const [name, root] of this.slotRoots) {
          if (obj === root) {
            this.onSlotPick?.(name);
            return;
          }
        }
        obj = obj.parent;
      }
    }
  }

  // ------------------------------------------------------------------ materials
  /** null → materials from the GLB (PBR); params → procedural toon (live-updatable). */
  setMaterial(params: ToonParams | null): void {
    this.needsRender = true;
    const modeChanged = (this.toonParams === null) !== (params === null)
      || this.toonParams?.outline_mode !== params?.outline_mode;
    this.toonParams = params ? { ...params } : null;
    if (modeChanged || !this.toonMaterial) this.applyMaterial();
    else this.updateMaterialUniforms();
  }

  private updateMaterialUniforms(): void {
    const p = this.toonParams;
    if (!p) return;
    for (const m of [this.toonMaterial, ...this.toonByColor.values()]) {
      if (m) updateToonMaterial(m, p, this.renderer.getPixelRatio());
    }
    if (this.hullMaterial) {
      this.hullMaterial.uniforms.uWidth.value = p.outline_width;
      (this.hullMaterial.uniforms.uColor.value as THREE.Color).set(p.outline_color);
    }
    for (const hull of this.hulls) hull.visible = p.outline_mode === "hull" && p.outline_width > 0;
    if (this.edgePass) {
      this.edgePass.uniforms.uPx.value = p.outline_px * this.renderer.getPixelRatio();
      (this.edgePass.uniforms.uColor.value as THREE.Color).set(p.outline_color);
    }
  }

  private applyMaterial(): void {
    for (const hull of this.hulls) hull.parent?.remove(hull);
    this.hulls = [];
    const p = this.toonParams;
    for (const mesh of this.visualMeshes) {
      if (mesh.userData.pbr === undefined) mesh.userData.pbr = mesh.material;
      mesh.material = mesh.userData.pbr as THREE.Material;
    }
    if (!p) {
      this.disableComposer();
      this.applyOptions();
      return;
    }
    this.toonMaterial ??= createToonMaterial(p);
    this.hullMaterial ??= createHullMaterial();
    for (const m of this.toonByColor.values()) m.dispose();
    this.toonByColor.clear();
    for (const mesh of this.visualMeshes) {
      mesh.material = this.toonFor(mesh, p);
      if (p.outline_mode === "hull" && !mesh.userData.no_outline) {        // face decals stay line-free
        ensureOutlineNormals(mesh.geometry as THREE.BufferGeometry);
        const skinned = mesh as THREE.SkinnedMesh;
        let hull: THREE.Mesh;
        if (skinned.isSkinnedMesh) {                                    // the outline shell follows the bones
          const shell = new THREE.SkinnedMesh(mesh.geometry, this.hullMaterial);
          shell.bind(skinned.skeleton, skinned.bindMatrix);
          hull = shell;
        } else {
          hull = new THREE.Mesh(mesh.geometry, this.hullMaterial);
        }
        hull.castShadow = false;
        hull.receiveShadow = false;
        hull.userData.isHull = true;
        mesh.add(hull);
        this.hulls.push(hull);
      }
    }
    if (p.outline_mode === "screen") this.enableComposer();
    else this.disableComposer();
    this.updateMaterialUniforms();
    this.applyOptions();
  }

  /** Registry models carry palette vertex colors; legacy models only material base colors. */
  private toonFor(mesh: THREE.Mesh, p: ToonParams): THREE.ShaderMaterial {
    if (mesh.geometry.getAttribute("color")) return this.toonMaterial!;
    const pbr = (Array.isArray(mesh.userData.pbr) ? mesh.userData.pbr[0] : mesh.userData.pbr) as THREE.MeshStandardMaterial;
    let color = pbr?.color ?? new THREE.Color(1, 1, 1);
    // old flat-color scenes often use Emission with a black base color → take the emissive color
    const luminance = (c: THREE.Color) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
    if (pbr?.emissive && luminance(color) < 0.02 && luminance(pbr.emissive) > 0.02) color = pbr.emissive;
    const key = color.getHexString();
    let material = this.toonByColor.get(key);
    if (!material) {
      material = createToonMaterial(p, false, color);
      this.toonByColor.set(key, material);
    }
    return material;
  }

  private enableComposer(): void {
    if (this.composer) return;
    const size = this.renderer.getDrawingBufferSize(new THREE.Vector2());
    this.normalTarget = new THREE.WebGLRenderTarget(size.x, size.y, { depthTexture: new THREE.DepthTexture(size.x, size.y) });
    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.edgePass = new ShaderPass(EDGE_SHADER);
    this.edgePass.uniforms.tNormal.value = this.normalTarget.texture;
    this.edgePass.uniforms.tDepth.value = this.normalTarget.depthTexture;
    this.composer.addPass(this.edgePass);
    this.composer.addPass(new OutputPass());
    this.resize();
  }

  private disableComposer(): void {
    for (const pass of this.composer?.passes ?? []) pass.dispose();
    this.composer?.dispose();
    this.normalTarget?.dispose();
    this.composer = null;
    this.edgePass = null;
    this.normalTarget = null;
  }

  private renderNormals(): void {
    if (!this.normalTarget) return;
    const hidden: THREE.Object3D[] = [this.ground, this.floorGrid, ...this.hulls, ...this.socketHelpers,
      ...this.collisionMeshes, ...(this.envelope ? [this.envelope] : []),
      ...(this.transformControls ? [this.transformControls.getHelper()] : [])];
    const visible = hidden.map((o) => o.visible);
    hidden.forEach((o) => { o.visible = false; });
    const background = this.scene.background;
    this.scene.background = null;
    this.scene.overrideMaterial = this.normalMaterial;
    this.renderer.setRenderTarget(this.normalTarget);
    this.renderer.setClearColor(0x000000, 1);
    this.renderer.clear();
    this.renderer.render(this.scene, this.camera);
    this.renderer.setRenderTarget(null);
    this.scene.overrideMaterial = null;
    this.scene.background = background;
    hidden.forEach((o, i) => { o.visible = visible[i]; });
    if (this.edgePass) {
      this.edgePass.uniforms.uNear.value = this.camera.near;
      this.edgePass.uniforms.uFar.value = this.camera.far;
    }
  }

  private addSocketHelper(node: THREE.Object3D): void {
    const helper = new THREE.Group();
    helper.add(new THREE.AxesHelper(1));
    const label = document.createElement("div");
    label.className = "socket-label";
    const socketType = (node.userData?.socket_type as string | undefined) ?? "";
    label.textContent = node.name.replace(/^socket_/, "") + (socketType && socketType !== "generic" ? ` · ${socketType}` : "");
    const labelObj = new CSS2DObject(label);
    labelObj.position.set(0, 1.1, 0);
    helper.add(labelObj);
    helper.userData.socket = node.name.replace(/^socket_/, "");
    const axes = helper.children[0] as THREE.AxesHelper;
    (axes.material as THREE.LineBasicMaterial).depthTest = false;
    axes.renderOrder = 20;
    node.add(helper);
    this.socketHelpers.push(helper);
  }

  private buildEnvelope(grid: [number, number, number], voxel: number): void {
    const [gx, gy, gz] = grid;
    const hx = (gx * voxel) / 2;
    const hz = (gz * voxel) / 2;
    const H = gy * voxel;
    const pts: number[] = [];
    const line = (a: number[], b: number[]) => pts.push(...a, ...b);
    for (let i = 0; i <= gx; i++) {
      const x = -hx + i * voxel;
      line([x, 0, -hz], [x, 0, hz]);          // bottom
      line([x, H, -hz], [x, H, hz]);          // top
      line([x, 0, -hz], [x, H, -hz]);         // back
      line([x, 0, hz], [x, H, hz]);           // front
    }
    for (let k = 0; k <= gz; k++) {
      const z = -hz + k * voxel;
      line([-hx, 0, z], [hx, 0, z]);
      line([-hx, H, z], [hx, H, z]);
      line([-hx, 0, z], [-hx, H, z]);         // left
      line([hx, 0, z], [hx, H, z]);           // right
    }
    for (let j = 0; j <= gy; j++) {
      const y = j * voxel;
      line([-hx, y, -hz], [hx, y, -hz]);
      line([-hx, y, hz], [hx, y, hz]);
      line([-hx, y, -hz], [-hx, y, hz]);
      line([hx, y, -hz], [hx, y, hz]);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    const color = new THREE.Color(cssVar("--accent", "#d9822b"));
    const cells = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.18 }));
    const boxGeometry = new THREE.BoxGeometry(hx * 2, H, hz * 2).translate(0, H / 2, 0);
    const box = new THREE.LineSegments(
      new THREE.EdgesGeometry(boxGeometry),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 }),
    );
    boxGeometry.dispose();
    this.envelope = new THREE.Group();
    this.envelope.add(cells, box);
    this.scene.add(this.envelope);
  }

  private setGroundSize(size: number): void {
    this.ground.scale.set(size * 3, 1, size * 3);
    this.scene.remove(this.floorGrid);
    disposeModelResources(this.floorGrid);
    const divisions = Math.round(size / 0.25);
    this.floorGrid = new THREE.GridHelper(size, divisions, cssVar("--grid-strong", "#777"), cssVar("--grid", "#999"));
    this.floorGrid.position.y = 0.001;
    const mat = this.floorGrid.material as THREE.LineBasicMaterial;
    mat.transparent = true;
    mat.opacity = 0.5;
    this.scene.add(this.floorGrid);
  }

  private fitShadow(): void {
    const center = this.bounds.getCenter(new THREE.Vector3());
    const r = this.radius * 1.6;
    this.sun.position.copy(center).addScaledVector(SUN_DIRECTION, r * 4);
    this.sun.target.position.copy(center);
    const cam = this.sun.shadow.camera;
    cam.left = cam.bottom = -r;
    cam.right = cam.top = r;
    cam.near = 0.01;
    cam.far = r * 10;
    cam.updateProjectionMatrix();
  }

  // ------------------------------------------------------------------ options
  setOption<K extends keyof ViewerOptions>(key: K, value: ViewerOptions[K]): void {
    this.options[key] = value;
    this.applyOptions();
  }

  private applyOptions(): void {
    this.needsRender = true;
    const o = this.options;
    for (const mesh of this.visualMeshes) {
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const m of materials) (m as THREE.MeshStandardMaterial).wireframe = o.wireframe;
    }
    for (const hull of this.hulls) hull.visible = !o.wireframe && this.toonParams?.outline_mode === "hull" && this.toonParams.outline_width > 0;
    for (const mesh of this.collisionMeshes) mesh.visible = o.collision;
    for (const helper of this.socketHelpers) helper.visible = o.sockets;
    if (this.envelope) this.envelope.visible = o.grid;
    if (this.skeletonHelper) this.skeletonHelper.visible = o.skeleton;
    this.controls.autoRotate = o.autoRotate;
  }

  // ------------------------------------------------------------------ camera
  /** Frame the joint's entire travel, so aiming never crops a long barrel. */
  private fitAimingBounds(): number | null {
    if (!this.aimJoints.length || !this.model) return null;
    const steps = (axis: "yaw" | "pitch") => Math.max(1, ...this.aimJoints.filter((j) => j.axis === axis)
      .map((j) => Math.ceil((j.max - j.min) / 15)));
    const yawSteps = steps("yaw"), pitchSteps = steps("pitch");
    const swept = this.bounds.clone();
    const corners: THREE.Vector3[] = [];
    const rotation = new THREE.Quaternion();
    const axis = new THREE.Vector3();
    for (let y = 0; y <= yawSteps; y++) {
      for (let p = 0; p <= pitchSteps; p++) {
        for (const joint of this.aimJoints) {
          const angle = THREE.MathUtils.lerp(joint.min, joint.max, joint.axis === "yaw" ? y / yawSteps : p / pitchSteps);
          axis.set(joint.axis === "pitch" ? 1 : 0, joint.axis === "yaw" ? 1 : 0, 0);
          rotation.setFromAxisAngle(axis, THREE.MathUtils.degToRad((angle - joint.value) * joint.sign));
          joint.object.quaternion.copy(joint.base).multiply(rotation);
        }
        this.model.updateMatrixWorld(true);
        for (const mesh of this.visualMeshes) {
          const box = mesh.geometry.boundingBox;
          if (!box) continue;
          swept.union(box.clone().applyMatrix4(mesh.matrixWorld));
          for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
            corners.push(new THREE.Vector3(x, y, z).applyMatrix4(mesh.matrixWorld));
          }
        }
      }
    }
    for (const joint of this.aimJoints) joint.object.quaternion.copy(joint.base);
    this.model.updateMatrixWorld(true);
    // Small allowance for angular extrema between the sampled poses.
    this.bounds.copy(swept).expandByScalar(swept.getSize(new THREE.Vector3()).length() * .01);
    const center = this.bounds.getCenter(new THREE.Vector3());
    let radius = 0;
    for (const corner of corners) radius = Math.max(radius, corner.distanceTo(center));
    return radius * 1.02;
  }

  preset(name: ViewPreset): void {
    const center = this.bounds.getCenter(new THREE.Vector3());
    const verticalFov = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const fitFov = Math.min(verticalFov, Math.atan(Math.tan(verticalFov) * this.camera.aspect));
    const dist = (this.radius / Math.sin(fitFov)) * 1.08;
    this.camera.position.copy(center).addScaledVector(PRESET_DIRECTIONS[name], dist);
    this.camera.near = Math.max(0.005, dist / 200);
    this.camera.far = dist * 50;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.update();
  }

  reset(): void {
    this.preset(this.initialPreset);
  }

  copyCameraFrom(other: Viewer): void {
    this.syncing = true;
    this.camera.position.copy(other.camera.position);
    this.camera.quaternion.copy(other.camera.quaternion);
    this.camera.near = other.camera.near;
    this.camera.far = other.camera.far;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(other.controls.target);
    this.controls.update();
    this.syncing = false;
  }

  // ------------------------------------------------------------------ animation
  play(name: string): void {
    this.needsRender = true;
    let started = false;
    for (const m of this.mixers) {
      const clip = m.clips.find((c) => c.name === name);
      if (!clip) continue;
      m.action?.stop();
      m.action = m.mixer.clipAction(clip);
      const loop = this.clipLoops.get(name) ?? true;
      m.action.clampWhenFinished = !loop;
      m.action.reset().setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, loop ? Infinity : 1).play();
      started = true;
    }
    if (started) this.playing = true;
  }

  togglePlay(): boolean {
    if (!this.mixers.some((m) => m.action)) return false;
    this.playing = !this.playing;
    this.needsRender = true;
    for (const m of this.mixers) if (m.action) {
      if (this.playing && m.action.loop === THREE.LoopOnce && m.action.time >= m.action.getClip().duration) m.action.reset().play();
      m.action.paused = !this.playing;
    }
    return this.playing;
  }

  isPlaying(): boolean {
    return this.playing;
  }

  /** A manual aiming change pauses the demo and rotates the real exported joints. */
  setAim(axis: "yaw" | "pitch", degrees: number): void {
    if (!Number.isFinite(degrees)) return;
    if (this.playing) this.togglePlay();
    for (const joint of this.aimJoints) {
      if (joint.axis === axis) joint.angle = THREE.MathUtils.clamp(degrees, joint.min, joint.max);
      const rotationAxis = new THREE.Vector3(joint.axis === "pitch" ? 1 : 0, joint.axis === "yaw" ? 1 : 0, 0);
      joint.object.quaternion.copy(joint.base).multiply(new THREE.Quaternion().setFromAxisAngle(rotationAxis,
        THREE.MathUtils.degToRad((joint.angle - joint.value) * joint.sign)));
    }
    this.model?.updateMatrixWorld(true);
    this.needsRender = true;
  }

  // ------------------------------------------------------------------ theme / loop
  applyTheme(): void {
    this.needsRender = true;
    this.scene.background = new THREE.Color(cssVar("--viewer-bg", "#20242a"));
    (this.ground.material as THREE.MeshStandardMaterial).color.set(cssVar("--viewer-ground", "#3a3f46"));
    if (this.model) this.setGroundSize(Math.max(4, Math.ceil(this.radius * 6)));
  }

  private resize(): void {
    if (this.disposed) return;
    this.needsRender = true;
    const w = Math.max(this.el.clientWidth, 1);
    const hgt = Math.max(this.el.clientHeight, 1);
    this.renderer.setSize(w, hgt, false);
    this.renderer.domElement.style.width = `${w}px`;
    this.renderer.domElement.style.height = `${hgt}px`;
    this.labels.setSize(w, hgt);
    this.camera.aspect = w / hgt;
    this.camera.updateProjectionMatrix();
    if (this.composer && this.normalTarget && this.edgePass) {
      const size = this.renderer.getDrawingBufferSize(new THREE.Vector2());
      this.composer.setPixelRatio(this.renderer.getPixelRatio());
      this.composer.setSize(w, hgt);
      this.normalTarget.setSize(size.x, size.y);
      (this.edgePass.uniforms.uResolution.value as THREE.Vector2).set(size.x, size.y);
    }
  }

  private animate = (): void => {
    if (this.disposed) return;
    this.frame = requestAnimationFrame(this.animate);
    this.timer.update();
    if (document.hidden || !this.visible || this.contextLost || !this.el.clientWidth || !this.el.clientHeight) return;
    const dt = this.timer.getDelta();
    if (this.playing) for (const m of this.mixers) m.mixer.update(dt);
    this.controls.update(dt);
    if (!this.needsRender && !this.playing && !this.controls.autoRotate) return;
    this.needsRender = false;
    this.selectionBox?.update();
    if (this.composer) {
      this.renderNormals();
      this.composer.render(dt);
    } else {
      this.renderer.render(this.scene, this.camera);
    }
    this.labels.render(this.scene, this.camera);
  };

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.loadToken++;
    cancelAnimationFrame(this.frame);
    this.resizeObserver.disconnect();
    this.intersectionObserver.disconnect();
    this.timer.dispose();
    this.clearModel();
    this.disableComposer();
    this.toonMaterial?.dispose();
    for (const m of this.toonByColor.values()) m.dispose();
    this.hullMaterial?.dispose();
    this.normalMaterial.dispose();
    disposeModelResources(this.ground);
    disposeModelResources(this.floorGrid);
    this.sun.shadow.dispose();
    if (this.transformControls) {
      this.scene.remove(this.transformControls.getHelper());
      this.transformControls.dispose();
      this.transformControls = null;
    }
    this.controls.dispose();
    this.scene.environment = null;
    this.environmentTarget?.dispose();
    this.environmentTarget = null;
    this.renderer.dispose();
    // dispose() keeps the WebGL context alive; browsers allow ~16, then drop the oldest ones.
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
    this.labels.domElement.remove();
  }
}
