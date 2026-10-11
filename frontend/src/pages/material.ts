import { entityTitle, parameterLabel, ui } from "../i18n";
// Shader lab: material variants tree, live toon on any built model, sliders → new variant.

import { api, ApiError, KIND_LABEL, type ParamSpec, type Tree, type VariantDetail } from "../api";
import { fmtValue, h, mount, statusBadge, toast } from "../dom";
import { onBuildEvent } from "../events";
import { toToonParams } from "../toon";
import { renderTree } from "../tree";
import { ViewerPanel, refreshPresets } from "../viewerPanel";
import { renderPreviews } from "../previews";

const MODEL_KEY = "var.lab.model";
const GROUPS: [string, string[]][] = [
  [ui("material.bands"), ["bands", "softness", "band_bias"]],
  [ui("material.light"), ["shadow_color", "shadow_strength", "light_tint"]],
  [ui("material.specular"), ["specular", "specular_size"]],
  [ui("material.rim"), ["rim", "rim_width", "rim_color"]],
  [ui("material.halftone"), ["halftone", "halftone_scale"]],
  [ui("material.outline"), ["outline_mode", "outline_width", "outline_px", "outline_color"]],
];

interface ModelChoice {
  label: string;
  url: string;
}

function safeGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

function safeSet(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
}

export async function renderMaterial(root: HTMLElement, id: string, query: URLSearchParams): Promise<() => void> {
  const [entity, initialTree, comps, assets] = await Promise.all([
    api.entity("materials", id), api.tree("materials", id), api.list("components"), api.list("assets"),
  ]);
  if (!root.isConnected) return () => {};
  let disposed = false;
  let selectedRequest = 0;
  let selectionVersion = 0;
  let centerRequest = 0;
  let modelRequest = 0;
  let diffRequest = 0;
  let treeRequest = 0;
  let saving = false;
  let patching = false;
  let rebuilding = false;
  const active = () => !disposed && root.isConnected;
  const reportError = (error: unknown) => {
    if (active()) toast(error instanceof ApiError ? error.errors.join("; ") || error.message : error instanceof Error ? error.message : String(error), "error");
  };
  let tree: Tree = initialTree;
  let selected: string | null = query.get("v") ?? pickDefault(tree);
  let compare: string | null = query.get("cmp");
  let pbrCompare = false;
  let detail: VariantDetail | null = null;
  let edited: Record<string, unknown> = {};
  let note = "";

  const catalog: ModelChoice[] = [...assets, ...comps]
    .filter((e) => !e.abstract && e.preview?.model)
    .map((e) => ({ label: `${KIND_LABEL[e.kind]}: ${entityTitle(e)} (${e.id}@${e.preview!.vid})`, url: e.preview!.model! }));
  let modelUrl = safeGet(MODEL_KEY) ?? catalog[0]?.url ?? "";

  const treePane = h("aside", { class: "pane tree-pane" });
  const center = h("section", { class: "pane center-pane" });
  const side = h("aside", { class: "pane side-pane" });
  const diffBox = h("div", { class: "diff-box" });
  const docDrawer = h("div", { class: "doc-drawer", hidden: true },
    h("strong", null, ui("material.description")), h("pre", { class: "markdown" }, entity.markdown));

  mount(root, h("section", { class: "page page-entity" },
    h("div", { class: "entity-head" },
      h("div", null,
        h("div", { class: "crumbs" }, h("a", { href: "#/materials" }, ui("nav.materials")), " / ", h("span", { class: "mono" }, entity.id)),
        h("h1", null, entityTitle(entity), h("span", { class: "chip chip-structure head-chip" }, `shader: ${entity.shader ?? "?"}`)),
        h("div", { class: "muted small" }, ui("material.liveHelp"),
          ui("material.previewHelp"))),
      h("div", { class: "btn-group" }, h("button", { class: "btn", onClick: () => { docDrawer.hidden = !docDrawer.hidden; } }, ui("common.description"))),
    ),
    docDrawer,
    h("div", { class: "entity-layout" }, treePane, center, side),
  ));

  const main = new ViewerPanel("", { materialSelect: false });
  let second: ViewerPanel | null = null;

  // ------------------------------------------------------------------ model / viewers
  const modelChoices = (): ModelChoice[] => {
    const fromVariant = (detail?.models ?? []).map((m) => ({ label: ui("dynamic.preview", { ref: m.ref }), url: m.url }));
    const seen = new Set(fromVariant.map((m) => m.url));
    return [...fromVariant, ...catalog.filter((m) => !seen.has(m.url))];
  };

  const loadModels = async () => {
    if (!active() || !modelUrl) return;
    const token = ++modelRequest;
    const panel = second;
    const url = modelUrl;
    await Promise.all([main.show(url, {}), panel ? panel.show(url, {}) : Promise.resolve()]);
    if (active() && token === modelRequest && panel && panel === second) panel.viewer.copyCameraFrom(main.viewer);
  };

  const applyMain = () => { if (active()) main.viewer.setMaterial(toToonParams(edited)); };

  const layoutCenter = () => {
    const twin = Boolean(compare && selected) || pbrCompare;
    if (twin && !second) {
      second = new ViewerPanel("", { materialSelect: false });
      const a = main;
      const b = second;
      a.viewer.onCameraChange = () => b.viewer.copyCameraFrom(a.viewer);
      b.viewer.onCameraChange = () => a.viewer.copyCameraFrom(b.viewer);
      a.onOptionChange = (k, v) => b.setOption(k, v);
      b.onOptionChange = (k, v) => a.setOption(k, v);
    }
    if (!twin && second) {
      second.dispose();
      second = null;
      main.viewer.onCameraChange = null;
      main.onOptionChange = null;
    }
    const choices = modelChoices();
    if (!choices.some((c) => c.url === modelUrl) && choices[0]) modelUrl = choices[0].url;
    const modelSelect = h("select", {
      class: "select-sm model-select",
      onChange: (ev: Event) => {
        modelUrl = (ev.target as HTMLSelectElement).value;
        safeSet(MODEL_KEY, modelUrl);
        void loadModels().catch(reportError);
      },
    }, choices.map((c) => h("option", { value: c.url, selected: c.url === modelUrl }, c.label)));
    main.setCaption(`${id}@${selected ?? "?"}${Object.keys(changedKeys()).length ? ui("core.modified") : ""}`);
    if (second) second.setCaption(pbrCompare ? ui("material.pbr") : `${id}@${compare}`);
    mount(center,
      h("div", { class: "pane-head" },
        h("span", { class: "muted small" }, ui("material.model")), modelSelect,
        h("button", {
          class: `btn btn-sm btn-toggle${pbrCompare ? " active" : ""}`, title: ui("material.pbrHint"),
          onClick: () => { pbrCompare = !pbrCompare; if (pbrCompare) compare = null; syncUrl(); drawTree(); void refreshCenter().catch(reportError); },
        }, ui("material.compare")),
        compare ? h("button", { class: "btn btn-sm", onClick: closeCompare }, ui("material.closeCompare")) : null,
      ),
      second ? h("div", { class: "compare-grid" }, main.el, second.el) : main.el,
      compare ? diffBox : null,
    );
  };

  const refreshCenter = async () => {
    if (!active()) return;
    const token = ++centerRequest;
    layoutCenter();
    const panel = second;
    const compareVid = compare;
    const selectedVid = selected;
    await loadModels();
    if (!active() || token !== centerRequest || selectedVid !== selected || panel !== second) return;
    applyMain();
    if (panel) {
      if (pbrCompare) panel.viewer.setMaterial(null);
      else if (compareVid) {
        let d: VariantDetail;
        try { d = await api.variant("materials", id, compareVid); }
        catch (error) {
          if (!active() || token !== centerRequest || panel !== second || compareVid !== compare || selectedVid !== selected) return;
          throw error;
        }
        if (!active() || token !== centerRequest || panel !== second || compareVid !== compare || selectedVid !== selected) return;
        panel.viewer.setMaterial(toToonParams(d.params ?? {}));
        void drawDiff();
      }
    }
  };

  const drawDiff = async () => {
    if (!active() || !compare || !selected) return;
    const token = ++diffRequest;
    const selectedVid = selected;
    const compareVid = compare;
    const diff = await api.diff(`materials/${id}/${selectedVid}`, `materials/${id}/${compareVid}`).catch(() => null);
    if (!diff || !active() || token !== diffRequest || selectedVid !== selected || compareVid !== compare) return;
    mount(diffBox, h("table", { class: "table diff-table" },
      h("thead", null, h("tr", null, h("th", null, ui("dynamic.diff", { count: diff.changed })), h("th", null, `A · ${selected}`), h("th", null, `B · ${compare}`))),
      h("tbody", null, diff.rows.filter((r) => r.changed).map((r) => h("tr", { class: "changed" },
        h("td", { class: "mono" }, r.key), h("td", null, swatch(r.a), fmtValue(r.a)), h("td", null, swatch(r.b), fmtValue(r.b)))))));
  };

  // ------------------------------------------------------------------ tree / selection
  const syncUrl = () => {
    if (!active()) return;
    const params = new URLSearchParams();
    if (selected) params.set("v", selected);
    if (compare) params.set("cmp", compare);
    history.replaceState(null, "", `#/materials/${id}${params.toString() ? `?${params}` : ""}`);
  };

  const drawTree = () => {
    if (!active()) return;
    const focusedVariant = treePane.contains(document.activeElement)
      ? (document.activeElement as HTMLElement).dataset.variant : undefined;
    mount(treePane,
      h("div", { class: "pane-head" }, h("strong", null, ui("material.presets")), h("span", { class: "muted small" }, ui("material.compareHint"))),
      renderTree(tree.nodes, { selected, compare, onSelect: select }));
    if (focusedVariant) [...treePane.querySelectorAll<HTMLElement>("[data-variant]")]
      .find((row) => row.dataset.variant === focusedVariant)?.focus({ preventScroll: true });
  };

  const select = (vid: string, shift: boolean) => {
    if (!active()) return;
    const previous = selected;
    if (shift && selected && vid !== selected) {
      compare = compare === vid ? null : vid;
      pbrCompare = false;
    } else {
      selected = vid;
      if (compare === vid) compare = null;
    }
    if (selected !== previous) ++selectionVersion;
    syncUrl();
    drawTree();
    if (selected !== previous || !detail) void loadSelected().then((loaded) => { if (loaded) return refreshCenter(); }).catch(reportError);
    else void refreshCenter().catch(reportError);
  };

  const closeCompare = () => {
    compare = null;
    syncUrl();
    drawTree();
    void refreshCenter().catch(reportError);
  };

  // ------------------------------------------------------------------ side panel
  const changedKeys = (): Record<string, unknown> => {
    const base = detail?.params ?? {};
    return Object.fromEntries(Object.entries(edited).filter(([k, v]) => !same(v, base[k])));
  };

  const loadSelected = async () => {
    if (!active() || !selected) return false;
    const token = ++selectedRequest;
    const vid = selected;
    detail = null;
    saveBtn = null;
    dirtyInfo = null;
    rows.clear();
    mount(side, h("div", { class: "loading", role: "status" }, ui("material.loading")));
    let loaded: VariantDetail;
    try { loaded = await api.variant("materials", id, vid); }
    catch (error) {
      if (!active() || token !== selectedRequest || selected !== vid) return false;
      mount(side,
        h("p", { class: "error", role: "alert" }, ui("material.error")),
        h("button", { class: "btn", onClick: () => void loadSelected().then((ok) => { if (ok) return refreshCenter(); }).catch(reportError) }, ui("common.retry")));
      throw error;
    }
    if (!active() || token !== selectedRequest || selected !== vid) return false;
    detail = loaded;
    edited = { ...(detail.params ?? {}) };
    note = "";
    renderSide();
    return true;
  };

  const onParam = (name: string, value: unknown) => {
    if (!active() || !detail || detail.id !== selected) return;
    edited[name] = value;
    applyMain();
    updateDirty();
  };

  let saveBtn: HTMLButtonElement | null = null;
  let dirtyInfo: HTMLElement | null = null;
  const rows = new Map<string, HTMLElement>();
  const updateDirty = () => {
    const changed = changedKeys();
    const n = Object.keys(changed).length;
    if (saveBtn) { saveBtn.disabled = saving || n === 0; saveBtn.textContent = saving ? ui("common.saving") : ui("branch.save"); }
    for (const control of side.querySelectorAll<HTMLInputElement | HTMLSelectElement>("input, select")) control.disabled = saving;
    if (dirtyInfo) dirtyInfo.textContent = n ? ui("dynamic.changedFields", { fields: Object.keys(changed).join(", ") }) : ui("common.noChanges");
    for (const [name, row] of rows) row.classList.toggle("changed", name in changed);
    main.setCaption(`${id}@${selected}${n ? ui("core.modified") : ""}`);
  };

  const renderSide = () => {
    const d = detail;
    if (!active() || !d) return;
    const v = d.variant;
    rows.clear();
    saveBtn = h("button", { class: "btn btn-primary", disabled: true, onClick: () => void saveBranch() }, ui("branch.save"));
    dirtyInfo = h("div", { class: "muted small" });
    const noteInput = h("input", { type: "text", placeholder: ui("branch.newNote"), value: note,
      onInput: (ev: Event) => { note = (ev.target as HTMLInputElement).value; } });
    const r = d.report;
    mount(side,
      h("div", { class: "pane-head" }, h("h2", null, v.id), statusBadge(v.status, d.build_state),
        v.author === "llm" ? h("span", { class: "chip chip-llm" }, "llm") : null),
      h("div", { class: "muted small" }, v.note || "—"),
      h("div", { class: "actions" },
        saveBtn,
        h("button", { class: "btn", disabled: saving, onClick: () => { edited = { ...(d.params ?? {}) }; renderSide(); applyMain(); } }, ui("common.reset")),
        h("button", { class: "btn", disabled: rebuilding, title: ui("material.blenderPreview"), onClick: () => void rebuild() }, rebuilding ? ui("build.starting") : ui("build.rebuild")),
        v.status === "approved"
          ? h("button", { class: "btn", disabled: patching, onClick: () => void patch({ status: d.build_state === "ok" ? "built" : "draft" }) }, ui("entity.unapprove"))
          : h("button", { class: "btn btn-ok", disabled: patching, onClick: () => void patch({ status: "approved" }) }, ui("entity.approve")),
      ),
      noteInput,
      dirtyInfo,
      GROUPS.map(([title, names]) => h("div", { class: "section param-group" },
        h("h3", null, title),
        names.filter((n) => entity.params[n]).map((name) => {
          const row = paramControl(name, entity.params[name], edited[name], (value) => onParam(name, value));
          rows.set(name, row);
          return row;
        }))),
      h("div", { class: "section" },
        h("h3", null, "Blender (Eevee) ", r ? h("span", { class: `badge ${r.status === "ok" ? "badge-built" : "badge-failed"}` }, r.status) : null),
        d.urls ? renderPreviews(d.urls)
          : h("p", { class: "muted small" }, d.build_state === "queued" || d.build_state === "running" ? ui("material.renderQueued") : ui("material.notBuilt")),
        r?.error ? h("div", { class: "box box-error small" }, r.error) : null,
      ),
      h("div", { class: "section" },
        h("h3", null, "Godot 4"),
        h("div", { class: "links small" },
          ["toon.gdshader", "toon_outline.gdshader", "toon_screen_outline.gdshader"].map((f) =>
            [h("a", { href: `/api/materials/${id}/godot/${f}`, download: f }, f), " · "]),
          h("a", { href: `/api/materials/${id}/variants/${v.id}/godot.tres`, download: `${id}_${v.id}.tres` }, `${id}_${v.id}.tres`)),
        h("p", { class: "muted small" }, ui("material.exportHelp")),
      ),
    );
    updateDirty();
  };

  const saveBranch = async () => {
    if (!active() || !detail || saving || !Object.keys(changedKeys()).length) return;
    const parent = detail;
    const token = selectionVersion;
    saving = true;
    renderSide();
    try {
      const created = await api.createVariant("materials", id, {
        parent: parent.id, delta: changedKeys(), note: note.trim() || "из лаборатории", level: parent.variant.level,
      });
      if (!active()) return;
      toast(ui("dynamic.savedMaterial", { ref: `${id}@${created.id}` }), "ok");
      refreshPresets();
      await reloadTree();
      if (active() && selected === parent.id && token === selectionVersion) select(created.id, false);
    } catch (err) {
      reportError(err);
    } finally {
      saving = false;
      if (active()) renderSide();
    }
  };

  const rebuild = async () => {
    if (!active() || !detail || rebuilding) return;
    const vid = detail.id;
    rebuilding = true;
    renderSide();
    try {
      const res = await api.rebuild("materials", id, vid);
      if (!active()) return;
      toast(ui("dynamic.blenderRender", { ref: vid, state: res.state }));
      await reloadTree();
    } catch (error) { reportError(error); }
    finally { rebuilding = false; if (active()) renderSide(); }
  };

  const patch = async (body: Parameters<typeof api.patch>[3]) => {
    if (!active() || !detail || patching) return;
    const vid = detail.id;
    const token = selectedRequest;
    patching = true;
    renderSide();
    try {
      const updated = await api.patch("materials", id, vid, body);
      if (!active()) return;
      if (token === selectedRequest && selected === vid && detail?.id === vid) {
        const keep = changedKeys();
        detail = updated;
        edited = { ...(updated.params ?? {}), ...keep };
        renderSide();
      }
      await reloadTree();
      if (active()) refreshPresets();
    } catch (error) { reportError(error); }
    finally { patching = false; if (active()) renderSide(); }
  };

  const reloadTree = async () => {
    const token = ++treeRequest;
    const updated = await api.tree("materials", id);
    if (!active() || token !== treeRequest) return;
    tree = updated;
    drawTree();
  };

  // ------------------------------------------------------------------ events
  const onKey = (ev: KeyboardEvent) => {
    if (ev.key === "Escape" && compare) closeCompare();
  };
  document.addEventListener("keydown", onKey);
  let refreshTimer = 0;
  let refreshing = false;
  let refreshPending = false;
  const refresh = async () => {
    if (!active() || refreshing) return;
    refreshing = true;
    refreshPending = false;
    try {
      await reloadTree();
      if (!active() || !selected || !detail) return;
      const vid = selected;
      const token = ++selectedRequest;
      const updated = await api.variant("materials", id, vid);
      if (!active() || token !== selectedRequest || selected !== vid || detail?.id !== vid) return;
      const keep = changedKeys();
      detail = updated;
      edited = { ...(updated.params ?? {}), ...keep };
      renderSide();
    } catch (error) { reportError(error); }
    finally {
      refreshing = false;
      if (active() && refreshPending) refreshTimer = window.setTimeout(() => void refresh(), 300);
    }
  };
  const offEvents = onBuildEvent((ev) => {
    if (ev.kind === "materials" && ev.id === id && active()) {
      refreshPending = true;
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => void refresh(), 300);
    }
  });
  const onTheme = () => { main.applyTheme(); second?.applyTheme(); };
  window.addEventListener("themechange", onTheme);

  const dispose = () => {
    if (disposed) return;
    disposed = true;
    ++selectedRequest;
    ++centerRequest;
    ++modelRequest;
    ++diffRequest;
    ++treeRequest;
    window.clearTimeout(refreshTimer);
    offEvents();
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("themechange", onTheme);
    main.dispose();
    second?.dispose();
  };
  try {
    drawTree();
    await loadSelected();
    await refreshCenter();
    if (!active()) dispose();
    return dispose;
  } catch (error) {
    dispose();
    throw error;
  }
}

function pickDefault(tree: Tree): string | null {
  const approved = tree.nodes.filter((n) => n.status === "approved");
  return (approved[0] ?? tree.nodes[0])?.id ?? null;
}

function same(a: unknown, b: unknown): boolean {
  if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) < 1e-9;
  return a === b;
}

function swatch(value: unknown): HTMLElement | null {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value)
    ? h("span", { class: "swatch", style: `background:${value}` }) : null;
}

function paramControl(name: string, spec: ParamSpec, value: unknown, onChange: (v: unknown) => void): HTMLElement {
  let control: HTMLElement;
  if (spec.type === "color") {
    const input = h("input", { type: "color", value: String(value), onInput: () => onChange(input.value) });
    control = input;
  } else if (spec.type === "enum") {
    const select = h("select", { onChange: () => onChange(select.value) },
      (spec.values ?? []).map((v) => h("option", { value: v, selected: v === value }, v)));
    control = select;
  } else if (spec.type === "bool") {
    const box = h("input", { type: "checkbox", checked: Boolean(value), onChange: () => onChange(box.checked) });
    control = box;
  } else {
    const isInt = spec.type === "int";
    const step = isInt ? 1 : Math.max(((spec.max ?? 1) - (spec.min ?? 0)) / 200, 0.001);
    
    const number = h("input", { type: "number", value: String(value), step: String(+step.toPrecision(2)), min: spec.min ?? undefined, max: spec.max ?? undefined });
    const range = h("input", { type: "range", value: String(value), step: String(+step.toPrecision(2)), min: spec.min ?? 0, max: spec.max ?? 1 });
    range.addEventListener("input", () => { number.value = range.value; onChange(range.valueAsNumber); });
    number.addEventListener("input", () => {
      const v = number.valueAsNumber;
      if (!Number.isNaN(v)) { range.value = number.value; onChange(v); }
    });
    control = h("div", { class: "num-input" }, range, number);
  }
  return h("div", { class: "lab-row", title: spec.description },
    h("span", { class: "param-name" }, parameterLabel(name)), control);
}
