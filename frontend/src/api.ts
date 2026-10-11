import { assertNoUiTokens, ui } from "./i18n";
// Typed client for the FastAPI backend.

export type Kind = "components" | "assets" | "materials" | "characters";
export type Status = "draft" | "built" | "failed" | "approved" | "archived";
export type BuildState = "none" | "queued" | "running" | "ok" | "failed" | "invalid";
export type Vec3 = [number, number, number];

export interface ParamSpec {
  type: "int" | "float" | "enum" | "bool" | "color";
  default: unknown;
  min: number | null;
  max: number | null;
  values: string[] | null;
  description: string;
  group?: string | null;
}

export interface Socket { name: string; type: string; position: Vec3; rotation: Vec3; description: string }
export interface Interface { grid_size: Vec3; voxel_size: number; pivot: string; mounts: string[]; sockets: Socket[] }
export interface SlotSpec { socket: string | null; accepts: string[]; max_grid: Vec3; required: boolean; description: string }

export interface EntitySummary {
  kind: Kind;
  id: string;
  title: string;
  type: "part" | "structure";
  category: string | null;
  inherits: string | null;
  abstract: boolean;
  complexity_level: number;
  tags: string[];
  variant_tags: string[];
  variant_count: number;
  status_counts: Record<string, number>;
  error: string | null;
  preview: { vid: string; status: Status; url: string | null; model: string | null } | null;
  character?: CharacterCard | null;
}

export interface CharacterCard { rig: string | null; clips: string[]; built_clips: string[]; polys: number | null }
export interface CharacterSpec { rig: string; clips: string[] }
export interface CastMember {
  ref: string; id: string; vid: string; title: string; hash: string | null; build_state: BuildState;
  model: string | null; preview: string | null; error: string | null;
}
export interface CharacterCast { title: string; note: string; spacing: number; members: CastMember[] }

export interface RegistrySettings { priority_tags: string[] }
export interface CatalogGroup { id: string; title: string; items: string[] }
export interface CatalogGroups { groups: CatalogGroup[] }
export interface BlockoutSheetMember {
  id: string; title: string; label: string; vid: string | null; ref: string | null;
  hash: string | null; model: string | null; url: string | null; preview: string | null;
  build_state: BuildState; params: Record<string, unknown>; dimensions: Vec3;
  bbox: { min: Vec3; max: Vec3 };
  position: Vec3; source_slots: string[]; error: string | null;
}
export interface BlockoutSheet {
  id: string; group_id: string; title: string; hash: string; snap_grid: number;
  layout: { columns: number; gap: number; bounds: Vec3 };
  members: BlockoutSheetMember[];
  related_assets: { id: string; title: string }[];
  context: { id: string; vid: string; ref: string; hash?: string } | null;
  blend: { url: string | null; available: boolean };
  previews?: import("./previews").PreviewUrls;
}
export interface AssetBlockoutSheets {
  groups: { id: string; title: string; component_count: number }[];
  context: BlockoutSheet["context"];
}
export interface BlockoutSheetBuild {
  sheet: BlockoutSheet;
  submitted: { ref: string; hash: string | null; state: string; error: string | null }[];
}
export interface BlockoutSheetBlender {
  sheet: BlockoutSheet;
  blend: { url: string; file: string };
  blender: BlenderSession | null;
}
export interface TagSummary {
  name: string;
  entity_count: number;
  variant_count: number;
  entities: { kind: "components" | "assets"; id: string }[];
}
export interface TagCatalog { tags: TagSummary[] }
export interface TagChange {
  old_name: string;
  name: string | null;
  changed_entities: number;
  changed_variants: number;
}

export interface ComposeOption {
  ref: string;
  kind: "components" | "assets";
  id: string;
  title: string;
  variant: string;
  status: Status;
  grid_size: Vec3;
  mounts: string[];
  sockets: Socket[];
  preview: string | null;
  built: boolean;
  type: "part" | "structure";
}

export interface NewAssetBody {
  id: string;
  title: string;
  description: string;
  grid_size: Vec3;
  voxel_size: number;
  pivot: "bottom_center" | "ground";
  sockets: Socket[];
  slots: Record<string, { socket: string | null; accepts: string[]; max_grid: Vec3; required: boolean; description: string }>;
  variant: {
    slots: Record<string, string | null>;
    slot_offsets: Record<string, Vec3>;
    level: number;
    note: string;
    tags: string[];
  };
  build: boolean;
}

export interface CreatedAsset extends VariantDetail { entity: EntityDoc; submit?: unknown }

export interface EntityDoc {
  kind: Kind;
  id: string;
  title: string;
  type: "part" | "structure";
  inherits: string | null;
  abstract: boolean;
  category: string | null;
  generator_version: number;
  interface: Interface | null;
  params: Record<string, ParamSpec>;
  slots: Record<string, SlotSpec>;
  complexity_level: number;
  tags: string[];
  shader: string | null;
  preview: string[];
  character?: CharacterSpec | null;
  chain: string[];
  description: string;
  frontmatter: Record<string, unknown>;
  markdown: string;
}

export interface TreeNode {
  id: string;
  parent: string | null;
  status: Status;
  level: number;
  rating: number | null;
  tags: string[];
  note: string;
  author: string;
  created: string | null;
  hash: string | null;
  build_state: BuildState;
  error: string | null;
  preview: string | null;
}

export interface Tree { nodes: TreeNode[]; edges: { from: string; to: string }[] }

export interface Check { name: string; ok: boolean; message: string }
export interface Stats {
  faces: number;
  tris: number;
  verts: number;
  objects: number;
  bbox_m: Vec3;
  bbox_vox: Vec3;
  envelope_m: Vec3;
  sockets: { name: string; position: Vec3 }[];
  animations: { name: string; frames: [number, number]; seconds?: number; nodes?: number }[];
}
export interface StructureReport {
  status: "ok" | "fail" | "skipped" | "not_run";
  purpose?: string;
  parts?: Record<string, number>;
  issues: { type: string; objects: string[]; message: string }[];
  verified: { relation: string; status: string; instances?: number; reason?: string }[];
  limitations?: string[];
}
export interface CompositionReport {
  status: "ok" | "fail";
  read_at_glance: string;
  primary_mass: string;
  hero_feature: string;
  secondary_features: string[];
  quiet_zones: string[];
  metrics: {
    large_attachments: number;
    roof_density: number;
    front_density: number;
    empty_socket_ratio: number;
    available_sockets: number;
    used_sockets: number;
  };
}
export interface Report {
  status: "ok" | "failed";
  error: string | null;
  checks: Check[];
  stats: Partial<Stats>;
  duration_s?: number;
  built_at?: string;
  blender_version?: string;
  log_tail?: string[];
  structure?: StructureReport;
  composition?: CompositionReport;
}

export interface SlotResolution {
  name: string;
  socket: string | null;
  host: string | null;
  ref: string | null;
  source: string;
  required: boolean;
  changed: boolean;
  component: string | null;
  variant: string | null;
  hash: string | null;
  params: Record<string, unknown> | null;
  offset: Vec3;
  offset_source: string;
}

export interface Urls {
  model: string;
  preview_iso: string;
  preview_front: string;
  preview_top: string;
  preview_bottom?: string;
  preview_back?: string;
  preview_right?: string;
  preview_left?: string;
  preview_34?: string;
  preview_side?: string;
  preview_pose?: string;
  report: string;
  log: string;
}

export interface VariantDetail {
  kind: Kind;
  entity_id: string;
  id: string;
  variant: {
    id: string;
    parent: string | null;
    level: number;
    author: string;
    note: string;
    tags: string[];
    rating: number | null;
    status: Status;
    created?: string | null;
    delta?: Record<string, unknown>;
    slots?: Record<string, string | null>;
    params_delta?: Record<string, unknown>;
    slot_offsets?: Record<string, Vec3>;
  };
  errors: string[];
  chain?: string[];
  params?: Record<string, unknown>;
  sources?: Record<string, string>;
  changed?: string[];
  changed_slots?: string[];
  slots?: SlotResolution[];
  hash?: string;
  build_state?: BuildState;
  report?: Report | null;
  urls?: Urls | null;
  shader?: string | null;
  models?: { ref: string; hash: string; url: string }[];
  // Manual geometry: the .blend used instead of the generator or slot assembly (own: declared by this variant).
  source?: { variant: string; file: string; own: boolean; open: boolean } | null;
  blender?: BlenderSession;
}

export interface BlenderSession {
  state: "opened" | "already_open" | "error";
  pid?: number;
  file?: string;
  error?: string;
}

export interface MaterialPreset {
  ref: string;
  id: string;
  vid: string;
  title: string;
  shader: string | null;
  note: string;
  status: Status;
  params: Record<string, unknown>;
}

export interface SlotOption {
  ref: string;
  component: string;
  variant: string;
  status: Status;
  rating: number | null;
  note: string;
  level: number;
  type: "part" | "structure";
  hash: string;
  preview: string | null;
  build_state: BuildState;
}

export interface DiffResult {
  a: { ref: string; hash: string };
  b: { ref: string; hash: string };
  rows: { key: string; a: unknown; b: unknown; changed: boolean }[];
  changed: number;
}

export interface NewVariantBody {
  parent: string | null;
  delta?: Record<string, unknown>;
  slots?: Record<string, string | null>;
  params_delta?: Record<string, unknown>;
  slot_offsets?: Record<string, Vec3>;
  note?: string;
  tags?: string[];
  level?: number;
  author?: "human" | "llm";
  build?: boolean;
}

export interface LegacySummary {
  id: string;
  source: string;
  folder: string;
  name: string;
  format: string;
  formats: string[];
  path: string;
  size: number;
  mtime: string;
  hash: string;
  state: "none" | "queued" | "running" | "ok" | "failed";
  error: string | null;
  preview: string | null;
  model: string | null;
  objects: number | null;
  tris: number | null;
  animated: boolean;
}

export interface LegacySource { name: string; label: string; path: string; exists: boolean }

export interface LegacyList {
  sources: LegacySource[];
  stats: { items: number; states: Record<string, number> };
  items: LegacySummary[];
}

export interface LegacyDetail extends LegacySummary {
  report: {
    status: string;
    error: string | null;
    file_version?: string;
    blender_version?: string;
    scene?: string;
    warnings?: string[];
    built_at?: string;
    duration_s?: number;
    log_tail?: string[];
    stats?: {
      objects: number; faces: number; tris: number; verts: number; bbox_m: Vec3;
      materials: string[]; actions: string[]; object_names: string[];
    };
  } | null;
  files: Record<string, string>;
  urls: import("./previews").PreviewUrls;
  log: string | null;
}

export interface BuildEvent {
  type: "build" | "variant" | "entity" | "legacy";
  item?: string;
  state: string;
  kind?: Kind;
  id?: string;
  vid?: string;
  hash?: string;
  cached?: boolean;
  error?: string | null;
  status?: Status;
  ts: string;
}


// ---------------------------------------------------------------------- Reference Lab
export interface RefSummary {
  id: string;
  title: string;
  usage: Record<string, boolean | undefined>;
  license: string;
  tags: string[];
  status: string;
  totals: Record<string, number>;
  preview: string | null;
  templates: string[];
}

export interface RefDetail extends RefSummary {
  metadata: Record<string, unknown>;
  analysis: any;
  semantic_yaml: string | null;
  semantic: { counts: Record<string, number>; landmarks: Record<string, number[]>; max_influences: number } | null;
  previews: string[];
  models: Record<string, string>;
  studies: Record<string, string[]>;
}

export interface TemplateSummary {
  kind: string;
  id: string;
  title: string;
  stats: any;
  pose: string | null;
  source: any;
  extraction: any;
  preview: string | null;
  model: string | null;
}

export interface LabCharacter {
  ref: string; id: string; vid: string; title: string; body_template: string; status: string;
  model: string | null; preview: string | null;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly errors: string[] = []) {
    super(message);
  }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  assertNoUiTokens(body);
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(ui("error.offline"), 0);
  }
  if (!res.ok) {
    let data: any = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    const errors: string[] = data?.errors
      ?? (Array.isArray(data?.detail) ? data.detail.map((d: any) => `${(d.loc ?? []).join(".")}: ${d.msg}`) : []);
    const message = errors.length ? errors.join("; ") : (typeof data?.detail === "string" ? data.detail
      : ui("error.server", { status: res.status }));
    throw new ApiError(message, res.status, errors);
  }
  return (await res.json()) as T;
}

export const api = {
  registrySettings: () => request<RegistrySettings>("GET", "/api/registry-settings"),
  saveRegistrySettings: (priorityTags: string[]) =>
    request<RegistrySettings>("PUT", "/api/registry-settings", { priority_tags: priorityTags }),
  catalogGroups: () => request<CatalogGroups>("GET", "/api/catalog-groups"),
  saveCatalogGroups: (groups: CatalogGroup[]) => request<CatalogGroups>("PUT", "/api/catalog-groups", { groups }),
  assetBlockoutSheets: (id: string, vid?: string | null) => request<AssetBlockoutSheets>("GET",
    `/api/assets/${encodeURIComponent(id)}/blockout-sheets${vid ? `?v=${encodeURIComponent(vid)}` : ""}`),
  blockoutSheet: (id: string, context: { asset?: string; v?: string } = {}) =>
    request<BlockoutSheet>("GET", sheetApiUrl(id, context)),
  buildBlockoutSheet: (id: string, context: { asset?: string; v?: string } = {}) =>
    request<BlockoutSheetBuild>("POST", sheetApiUrl(id, context, "/build")),
  openBlockoutSheet: (id: string, context: { asset?: string; v?: string } = {}, open = true) =>
    request<BlockoutSheetBlender>("POST", sheetApiUrl(id, context, "/blender"), { open }),
  blockoutSheetProjections: (id: string, context: { asset?: string; v?: string } = {}) =>
    request<BlockoutSheetBlender>("POST", sheetApiUrl(id, context, "/projections")),
  tags: async () => {
    try {
      return await request<TagCatalog>("GET", "/api/tags");
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.errors.some((message) => message.startsWith("path.kind:"))) {
        throw new ApiError(ui("error.oldApi"), error.status);
      }
      throw error;
    }
  },
  renameTag: (name: string, nextName: string) => request<TagChange>("PATCH", `/api/tags/${encodeURIComponent(name)}`, { name: nextName }),
  deleteTag: (name: string) => request<TagChange>("DELETE", `/api/tags/${encodeURIComponent(name)}`),
  composeOptions: async () => (await request<{ items: ComposeOption[] }>("GET", "/api/compose/options")).items,
  createAsset: (body: NewAssetBody) => request<CreatedAsset>("POST", "/api/assets", body),
  list: (kind: Kind) => request<EntitySummary[]>("GET", `/api/${kind}`),
  entity: (kind: Kind, id: string) => request<EntityDoc>("GET", `/api/${kind}/${id}`),
  tree: (kind: Kind, id: string) => request<Tree>("GET", `/api/${kind}/${id}/tree`),
  variant: (kind: Kind, id: string, vid: string) => request<VariantDetail>("GET", `/api/${kind}/${id}/variants/${vid}`),
  createVariant: (kind: Kind, id: string, body: NewVariantBody) =>
    request<VariantDetail>("POST", `/api/${kind}/${id}/variants`, body),
  openInBlender: (kind: Kind, id: string, vid: string, body: { fork: boolean; note?: string }) =>
    request<VariantDetail>("POST", `/api/${kind}/${id}/variants/${vid}/blender`, body),
  rebuild: (kind: Kind, id: string, vid: string) =>
    request<{ hash: string | null; state: string; error: string | null }>("POST", `/api/${kind}/${id}/variants/${vid}/rebuild`),
  patch: (kind: Kind, id: string, vid: string, body: Partial<{ rating: number | null; tags: string[]; status: Status; note: string }>) =>
    request<VariantDetail>("PATCH", `/api/${kind}/${id}/variants/${vid}`, body),
  diff: (a: string, b: string) => request<DiffResult>("GET", `/api/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  slotOptions: (id: string) => request<Record<string, SlotOption[]>>("GET", `/api/assets/${id}/slot-options`),
  previewUrl: (hash: string) => `/api/builds/${hash}/preview_iso.png`,
  materialPresets: () => request<MaterialPreset[]>("GET", "/api/material-presets"),
  characterCast: () => request<CharacterCast>("GET", "/api/character-cast"),
  references: () => request<{ references: RefSummary[]; templates: TemplateSummary[] }>("GET", "/api/references"),
  reference: (id: string) => request<RefDetail>("GET", `/api/references/${id}`),
  labCharacters: () => request<LabCharacter[]>("GET", "/api/reference-lab/characters"),
  legacyList: () => request<LegacyList>("GET", "/api/legacy"),
  legacyItem: (id: string) => request<LegacyDetail>("GET", `/api/legacy/items/${id}`),
  legacyBuild: (force = false) => request<{ queued: number }>("POST", `/api/legacy/build${force ? "?force=true" : ""}`),
  legacyRebuild: (id: string) => request<{ state: string }>("POST", `/api/legacy/items/${id}/rebuild`),
};

function sheetApiUrl(id: string, context: { asset?: string; v?: string }, suffix = ""): string {
  const query = new URLSearchParams();
  if (context.asset) query.set("asset", context.asset);
  if (context.v) query.set("v", context.v);
  return `/api/blockout-sheets/${encodeURIComponent(id)}${suffix}${query.size ? `?${query}` : ""}`;
}

export function blockoutSheetHref(id: string, asset?: string, vid?: string | null): string {
  const query = new URLSearchParams();
  if (asset) query.set("asset", asset);
  if (vid) query.set("v", vid);
  return `#/blockout/${encodeURIComponent(id)}${query.size ? `?${query}` : ""}`;
}

export const KIND_LABEL: Record<Kind, string> = {
  components: ui("nav.components"), assets: ui("nav.assets"), materials: ui("nav.materials"), characters: ui("nav.characters"),
};
