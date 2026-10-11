// Procedural toon — three.js implementation (same model as registry/materials/toon/blender.py
// and toon.gdshader). All parameters are uniforms, so sliders update without recompiling.

import * as THREE from "three";

export interface ToonParams {
  bands: number;
  softness: number;
  band_bias: number;
  shadow_color: string;
  shadow_strength: number;
  light_tint: string;
  specular: number;
  specular_size: number;
  rim: number;
  rim_width: number;
  rim_color: string;
  halftone: number;
  halftone_scale: number;
  outline_mode: "none" | "hull" | "screen";
  outline_width: number;
  outline_px: number;
  outline_color: string;
}

export const TOON_DEFAULTS: ToonParams = {
  bands: 3, softness: 0.02, band_bias: 0, shadow_color: "#3b4270", shadow_strength: 0.55,
  light_tint: "#fff6e8", specular: 0.25, specular_size: 0.12, rim: 0.2, rim_width: 0.3, rim_color: "#ffffff",
  halftone: 0, halftone_scale: 6, outline_mode: "hull", outline_width: 0.012, outline_px: 1.5, outline_color: "#1c1b22",
};

export function toToonParams(raw: Record<string, unknown>): ToonParams {
  return { ...TOON_DEFAULTS, ...(raw as Partial<ToonParams>) };
}

const TOON_VERT = /* glsl */ `
#include <common>
#include <color_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
varying vec3 vNormalV;
varying vec3 vViewPos;
void main() {
  #include <color_vertex>
  #include <beginnormal_vertex>
  #include <skinbase_vertex>
  #include <skinnormal_vertex>
  #include <defaultnormal_vertex>
  #include <begin_vertex>
  #include <skinning_vertex>
  #include <project_vertex>
  #include <worldpos_vertex>
  #include <shadowmap_vertex>
  vNormalV = normalize(transformedNormal);
  vViewPos = -mvPosition.xyz;
}`;

const TOON_FRAG = /* glsl */ `
#include <common>
#include <packing>
#include <color_pars_fragment>
#include <lights_pars_begin>
#include <shadowmap_pars_fragment>
#include <shadowmask_pars_fragment>
uniform int uBands;
uniform float uSoftness;
uniform float uBias;
uniform vec3 uShadowColor;
uniform float uShadowStrength;
uniform vec3 uLightTint;
uniform float uSpecular;
uniform float uSpecSize;
uniform float uRim;
uniform float uRimWidth;
uniform vec3 uRimColor;
uniform float uHalftone;
uniform float uHalftoneScale;
uniform float uPixelRatio;
uniform vec3 uAlbedo;
varying vec3 vNormalV;
varying vec3 vViewPos;

float toonBands(float x) {
  if (uBands <= 1) return 1.0;
  float s = max(uSoftness, 1e-4);
  float acc = 0.0;
  for (int k = 1; k < 6; k++) {
    if (k >= uBands) break;
    float b = float(k) / float(uBands);
    acc += smoothstep(b - s, b + s, x);
  }
  return acc / float(uBands - 1);
}

void main() {
  vec3 albedo = uAlbedo;           // material base color (legacy models) or white
  #if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
    albedo *= vColor.rgb;           // registry models: palette vertex colors
  #endif
  vec3 N = normalize(vNormalV);
  if (!gl_FrontFacing) N = -N;
  vec3 V = normalize(vViewPos);
  vec3 Ld = directionalLights[0].direction;
  float L = clamp(dot(N, Ld), 0.0, 1.0) * getShadowMask();
  float t = toonBands(clamp(L + uBias, 0.0, 1.0));
  vec3 dark = mix(vec3(1.0), uShadowColor, uShadowStrength);
  vec3 shade = mix(dark, uLightTint, t);
  if (uHalftone > 0.0) {
    vec2 cell = fract(gl_FragCoord.xy / (uHalftoneScale * uPixelRatio)) - 0.5;
    float radius = sqrt(1.0 - t) * 0.7 * uHalftone;
    float inside = 1.0 - smoothstep(radius - 0.05, radius + 0.05, length(cell));
    shade *= 1.0 - 0.55 * inside;
  }
  vec3 color = albedo * shade;
  float s2 = uSoftness * 0.5 + 0.005;
  if (uSpecular > 0.0 && L > 0.01) {
    float ndh = dot(N, normalize(Ld + V));
    float th = 1.0 - uSpecSize * 0.5;
    color += uLightTint * uSpecular * smoothstep(th - s2, th + s2, ndh);
  }
  if (uRim > 0.0) {
    float edge = smoothstep(1.0 - uRimWidth - s2, 1.0 - uRimWidth + s2, 1.0 - abs(dot(N, V)));
    color += uRimColor * uRim * edge * (0.35 + 0.65 * t);
  }
  gl_FragColor = vec4(color, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function createToonMaterial(params: ToonParams, vertexColors = true, albedo?: THREE.Color): THREE.ShaderMaterial {
  const material = new THREE.ShaderMaterial({
    uniforms: THREE.UniformsUtils.merge([
      THREE.UniformsLib.lights,
      {
        uBands: { value: 3 }, uSoftness: { value: 0 }, uBias: { value: 0 },
        uShadowColor: { value: new THREE.Color() }, uShadowStrength: { value: 0 },
        uLightTint: { value: new THREE.Color() }, uSpecular: { value: 0 }, uSpecSize: { value: 0 },
        uRim: { value: 0 }, uRimWidth: { value: 0 }, uRimColor: { value: new THREE.Color() },
        uHalftone: { value: 0 }, uHalftoneScale: { value: 6 }, uPixelRatio: { value: 1 },
        uAlbedo: { value: albedo ? albedo.clone() : new THREE.Color(1, 1, 1) },
      },
    ]),
    vertexShader: TOON_VERT,
    fragmentShader: TOON_FRAG,
    lights: true,
    vertexColors,
  });
  updateToonMaterial(material, params);
  return material;
}

export function updateToonMaterial(material: THREE.ShaderMaterial, p: ToonParams, pixelRatio = 1): void {
  const u = material.uniforms;
  u.uBands.value = p.bands;
  u.uSoftness.value = p.softness;
  u.uBias.value = p.band_bias;
  (u.uShadowColor.value as THREE.Color).set(p.shadow_color);
  u.uShadowStrength.value = p.shadow_strength;
  (u.uLightTint.value as THREE.Color).set(p.light_tint);
  u.uSpecular.value = p.specular;
  u.uSpecSize.value = p.specular_size;
  u.uRim.value = p.rim;
  u.uRimWidth.value = p.rim_width;
  (u.uRimColor.value as THREE.Color).set(p.rim_color);
  u.uHalftone.value = p.halftone;
  u.uHalftoneScale.value = p.halftone_scale;
  u.uPixelRatio.value = pixelRatio;
}

// ------------------------------------------------------------------ hull outline

const HULL_VERT = /* glsl */ `
#include <common>
#include <skinning_pars_vertex>
attribute vec3 outlineNormal;
uniform float uWidth;
void main() {
  #include <skinbase_vertex>
  vec3 transformed = position + outlineNormal * uWidth;   // pushed out in the bind pose, then skinned
  #include <skinning_vertex>
  gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
}`;

const HULL_FRAG = /* glsl */ `
uniform vec3 uColor;
void main() {
  gl_FragColor = vec4(uColor, 1.0);
  #include <colorspace_fragment>
}`;

export function createHullMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: { uWidth: { value: 0.012 }, uColor: { value: new THREE.Color() } },
    vertexShader: HULL_VERT,
    fragmentShader: HULL_FRAG,
    side: THREE.BackSide,
  });
}

/** Averaged normals per position: flat voxel meshes have split normals and the hull would crack. */
export function ensureOutlineNormals(geometry: THREE.BufferGeometry): void {
  if (geometry.getAttribute("outlineNormal")) return;
  const pos = geometry.getAttribute("position");
  const nrm = geometry.getAttribute("normal");
  const sums = new Map<string, THREE.Vector3>();
  const key = (i: number) => `${pos.getX(i).toFixed(4)},${pos.getY(i).toFixed(4)},${pos.getZ(i).toFixed(4)}`;
  const n = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    n.fromBufferAttribute(nrm, i);
    const k = key(i);
    const s = sums.get(k);
    if (s) s.add(n);
    else sums.set(k, n.clone());
  }
  const out = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    const s = sums.get(key(i))!;
    const len = s.length();
    if (len > 1e-3) s.divideScalar(len);
    else s.fromBufferAttribute(nrm, i);
    out.set([s.x, s.y, s.z], i * 3);
  }
  geometry.setAttribute("outlineNormal", new THREE.BufferAttribute(out, 3));
}

// ------------------------------------------------------------------ screen-space outline

export const EDGE_SHADER = {
  uniforms: {
    tDiffuse: { value: null as THREE.Texture | null },
    tNormal: { value: null as THREE.Texture | null },
    tDepth: { value: null as THREE.Texture | null },
    uResolution: { value: new THREE.Vector2(1, 1) },
    uPx: { value: 1.5 },
    uColor: { value: new THREE.Color() },
    uNear: { value: 0.1 },
    uFar: { value: 100 },
  },
  vertexShader: /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */ `
#include <packing>
uniform sampler2D tDiffuse;
uniform sampler2D tNormal;
uniform sampler2D tDepth;
uniform vec2 uResolution;
uniform float uPx;
uniform vec3 uColor;
uniform float uNear;
uniform float uFar;
varying vec2 vUv;
float viewZ(vec2 uv) {
  float d = texture2D(tDepth, uv).x;
  return -perspectiveDepthToViewZ(d, uNear, uFar);
}
void main() {
  vec4 base = texture2D(tDiffuse, vUv);
  vec2 px = uPx / uResolution;
  float d0 = viewZ(vUv);
  vec3 n0 = texture2D(tNormal, vUv).xyz * 2.0 - 1.0;
  float edge = 0.0;
  vec2 offs[4];
  offs[0] = vec2(px.x, 0.0); offs[1] = vec2(-px.x, 0.0); offs[2] = vec2(0.0, px.y); offs[3] = vec2(0.0, -px.y);
  for (int i = 0; i < 4; i++) {
    vec2 uv = vUv + offs[i];
    float d = viewZ(uv);
    vec3 n = texture2D(tNormal, uv).xyz * 2.0 - 1.0;
    edge = max(edge, step(0.02 * min(d0, d), abs(d - d0)));
    edge = max(edge, step(0.45, 1.0 - dot(n0, n)));
  }
  gl_FragColor = vec4(mix(base.rgb, uColor, edge), base.a);
}`,
};

/** Release owned GLB resources, including textures and helpers; viewer toon materials are shared. */
export function disposeModelResources(root: THREE.Object3D, originalKey?: string, shared: ReadonlySet<THREE.Material> = new Set()): void {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  const skeletons = new Set<THREE.Skeleton>();
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.geometry) geometries.add(mesh.geometry);
    for (const value of [mesh.material, originalKey ? obj.userData[originalKey] : null]) {
      for (const material of Array.isArray(value) ? value : [value]) {
        if (material && !shared.has(material)) materials.add(material);
      }
    }
    if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) skeletons.add((mesh as THREE.SkinnedMesh).skeleton);
  });
  for (const material of materials) {
    for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
    material.dispose();
  }
  const images = new Set<ImageBitmap>();
  for (const texture of textures) {
    texture.dispose();
    const data = texture.source.data;
    if (typeof ImageBitmap !== "undefined" && data instanceof ImageBitmap) images.add(data);
  }
  for (const image of images) image.close();
  for (const geometry of geometries) geometry.dispose();
  for (const skeleton of skeletons) skeleton.dispose();
}

