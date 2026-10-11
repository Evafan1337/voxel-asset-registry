import { ui } from "../i18n";
// Legacy: read-only catalog of models made before the registry (blend/fbx snapshots rendered by Blender).

import { api, type LegacyDetail, type LegacyList, type LegacySummary } from "../api";
import { debounce, h, mount, toast } from "../dom";
import { onBuildEvent } from "../events";
import { ViewerPanel } from "../viewerPanel";
import { renderPreviews } from "../previews";

interface Filters {
  query: string;
  source: string;
  format: string;
  animated: boolean;
}

const filters: Filters = { query: "", source: "", format: "", animated: false };
let lastOrder: string[] = [];           // for prev/next on the item page

const STATE_LABEL: Record<string, string> = { none: ui("common.noPreview"), queued: ui("status.queued"), running: ui("legacy.rendering"), failed: ui("status.failed") };

function fmtDate(iso: string): string {
  return iso.slice(0, 10);
}

function fmtSize(bytes: number): string {
  if (bytes >= 1 << 20) return ui("legacy.megabytes", { count: Math.round(bytes / (1 << 20) * 10) / 10 });
  return ui("legacy.kilobytes", { count: Math.max(1, Math.round(bytes / 1024)) });
}

function fmtCount(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return n >= 10000 ? `${(n / 1000).toFixed(0)}k` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function matches(item: LegacySummary): boolean {
  const q = filters.query.trim().toLowerCase();
  if (q && !`${item.folder}/${item.name}`.toLowerCase().includes(q)) return false;
  if (filters.source && item.source !== filters.source) return false;
  if (filters.format && !item.formats.includes(filters.format)) return false;
  if (filters.animated && !item.animated) return false;
  return true;
}

function card(item: LegacySummary): HTMLElement {
  const busy = item.state === "queued" || item.state === "running";
  return h("a", { class: `card legacy-card${item.state === "failed" ? " legacy-failed" : ""}`, href: `#/legacy/${item.id}`, title: item.path },
    h("div", { class: "card-thumb" },
      item.preview
        ? h("img", { src: item.preview, alt: item.name, loading: "lazy" })
        : h("div", { class: `thumb-empty${busy ? " badge-busy" : ""}` }, STATE_LABEL[item.state] ?? item.state),
      item.state === "failed" ? h("span", { class: "badge badge-failed card-badge", title: item.error ?? "" }, ui("status.failed")) : null,
      item.animated ? h("span", { class: "badge badge-built legacy-anim", title: ui("legacy.animatedHint") }, "▶") : null,
    ),
    h("div", { class: "card-body" },
      h("strong", { class: "legacy-name" }, item.name),
      h("div", { class: "chips" }, item.formats.map((f) => h("span", { class: "chip chip-socket" }, `.${f}`))),
      h("div", { class: "muted small" },
        item.objects !== null ? ui("legacy.objectSummary", { count: item.objects, tris: fmtCount(item.tris) }) : "",
        fmtDate(item.mtime)),
    ),
  );
}

export async function renderLegacy(root: HTMLElement): Promise<() => void> {
  let data: LegacyList = await api.legacyList();
  const statsBox = h("div", { class: "legacy-stats" });
  const toolbar = h("div", { class: "filter-bar" });
  const body = h("div", { class: "legacy-body" });

  const draw = () => {
    const visible = data.items.filter(matches);
    lastOrder = visible.map((i) => i.id);
    const st = data.stats.states;
    const missing = (st.none ?? 0);
    mount(statsBox,
      h("span", null, ui("legacy.modelCount", { count: data.stats.items })),
      h("span", { class: "st-ok" }, `✓ ${st.ok ?? 0}`),
      st.failed ? h("span", { class: "st-failed" }, `✗ ${st.failed}`) : null,
      (st.queued ?? 0) + (st.running ?? 0) ? h("span", { class: "badge badge-busy" }, ui("legacy.renderCount", { count: (st.queued ?? 0) + (st.running ?? 0) })) : null,
      missing ? h("button", { class: "btn btn-sm btn-primary", onClick: () => void buildMissing() }, ui("legacy.renderMissingCount", { count: missing })) : null,
    );

    const search = h("input", { type: "text", placeholder: ui("legacy.search"), value: filters.query, class: "legacy-search" });
    search.addEventListener("input", debounce(() => { filters.query = search.value; drawBody(); }, 150));
    mount(toolbar,
      h("div", { class: "chips" },
        search,
        chip(ui("legacy.sources"), filters.source === "", () => { filters.source = ""; draw(); }),
        data.sources.map((s) => chip(s.label, filters.source === s.name, () => { filters.source = s.name; draw(); })),
      ),
      h("div", { class: "chips" },
        chip(ui("legacy.formatsAll"), filters.format === "", () => { filters.format = ""; draw(); }),
        ["blend", "fbx"].map((f) => chip(`.${f}`, filters.format === f, () => { filters.format = f; draw(); })),
        chip(ui("legacy.animated"), filters.animated, () => { filters.animated = !filters.animated; draw(); }),
      ),
    );
    drawBody();
  };

  const drawBody = () => {
    const visible = data.items.filter(matches);
    lastOrder = visible.map((i) => i.id);
    if (!visible.length) {
      mount(body, h("p", { class: "muted" }, ui("common.noResults")));
      return;
    }
    const sections: HTMLElement[] = [];
    for (const src of data.sources) {
      const ofSource = visible.filter((i) => i.source === src.name);
      if (!ofSource.length) continue;
      const folders = new Map<string, LegacySummary[]>();
      for (const item of ofSource) {
        if (!folders.has(item.folder)) folders.set(item.folder, []);
        folders.get(item.folder)!.push(item);
      }
      sections.push(h("section", { class: "legacy-source" },
        h("h2", null, src.label, h("span", { class: "muted small mono" }, `  ${src.path}`)),
        [...folders.entries()].map(([folder, items]) => h("div", { class: "legacy-folder" },
          h("h3", { class: "mono" }, folder || ui("legacy.root"), h("span", { class: "tab-count" }, String(items.length))),
          h("div", { class: "card-grid legacy-grid" }, items.map(card)),
        )),
      ));
    }
    mount(body, sections);
  };

  const buildMissing = async () => {
    const res = await api.legacyBuild();
    toast(ui("legacy.queuedCount", { count: res.queued }));
    await reload();
  };

  const reload = async () => {
    data = await api.legacyList();
    draw();
  };

  mount(root, h("section", { class: "page page-legacy" },
    h("div", { class: "entity-head" },
      h("div", null,
        h("h1", null, "Legacy"),
        h("div", { class: "muted small" },
          ui("legacy.help"))),
      statsBox,
    ),
    toolbar,
    body,
  ));
  draw();

  const refresh = debounce(() => void reload(), 800);
  const off = onBuildEvent((ev) => {
    if (ev.type === "legacy") refresh();
  });
  return off;
}

function chip(label: string, active: boolean, onClick: () => void): HTMLElement {
  return h("button", { class: `chip chip-toggle${active ? " active" : ""}`, onClick }, label);
}

// ------------------------------------------------------------------ item page

export async function renderLegacyItem(root: HTMLElement, id: string): Promise<() => void> {
  let item: LegacyDetail = await api.legacyItem(id);
  if (!lastOrder.length) {
    lastOrder = (await api.legacyList()).items.filter(matches).map((i) => i.id);
  }
  const panel = new ViewerPanel();
  const side = h("aside", { class: "pane side-pane" });
  const center = h("section", { class: "pane center-pane" }, panel.el);

  const pos = lastOrder.indexOf(id);
  const prev = pos > 0 ? lastOrder[pos - 1] : null;
  const next = pos >= 0 && pos < lastOrder.length - 1 ? lastOrder[pos + 1] : null;
  const onKey = (ev: KeyboardEvent) => {
    if ((ev.target as HTMLElement).tagName === "INPUT") return;
    if (ev.key === "ArrowLeft" && prev) location.hash = `#/legacy/${prev}`;
    if (ev.key === "ArrowRight" && next) location.hash = `#/legacy/${next}`;
  };
  document.addEventListener("keydown", onKey);

  const drawSide = () => {
    const r = item.report;
    const s = r?.stats;
    mount(side,
      h("div", { class: "pane-head" }, h("h2", null, item.name),
        item.state !== "ok" ? h("span", { class: `badge ${item.state === "failed" ? "badge-failed" : "badge-busy"}` }, STATE_LABEL[item.state] ?? item.state) : null),
      h("div", { class: "muted small mono legacy-path" }, item.path),
      h("div", { class: "actions" },
        h("button", { class: "btn", onClick: () => void rebuild() }, item.state === "none" ? ui("legacy.render") : ui("legacy.rerender")),
        h("button", { class: "btn btn-ghost", title: ui("legacy.copyPath"), onClick: () => void copyPath() }, ui("legacy.path")),
      ),
      r?.error ? h("div", { class: "box box-error small" }, r.error) : null,
      r?.warnings?.length ? h("div", { class: "muted small" }, r.warnings.join("; ")) : null,
      h("div", { class: "section" },
        h("h3", null, ui("legacy.file")),
        h("dl", { class: "stats" },
          stat(ui("legacy.formats"), item.formats.map((f) => `.${f}`).join(" + ")),
          stat(ui("legacy.renderFrom"), `.${item.format}`),
          stat(ui("legacy.size"), fmtSize(item.size)),
          stat(ui("legacy.modified"), item.mtime.replace("T", " ").replace("+00:00", " UTC")),
          stat(ui("legacy.version"), r?.file_version ? `Blender ${r.file_version}` : null),
          stat(ui("legacy.scene"), r?.scene),
        )),
      s ? h("div", { class: "section" },
        h("h3", null, ui("legacy.geometry")),
        h("dl", { class: "stats" },
          stat(ui("legacy.objects"), s.objects),
          stat(ui("stats.polygons"), `${s.faces} (${s.tris} tris)`),
          stat(ui("stats.vertices"), s.verts),
          stat(ui("stats.boundsM"), s.bbox_m.join(" × ")),
          stat(ui("viewer.animation"), s.actions.length ? s.actions.join(", ") : "—"),
        ),
        s.materials.length ? h("details", null, h("summary", { class: "small" }, ui("legacy.materialCount", { count: s.materials.length })),
          h("div", { class: "chips" }, s.materials.map((m) => h("span", { class: "chip" }, m)))) : null,
        h("details", null, h("summary", { class: "small" }, s.objects > s.object_names.length
          ? ui("legacy.objectCountOf", { count: s.object_names.length, total: s.objects })
          : ui("legacy.objectCount", { count: s.object_names.length })),
          h("div", { class: "chips" }, s.object_names.map((n) => h("span", { class: "chip" }, n)))),
      ) : null,
      Object.keys(item.urls).length ? h("div", { class: "section" },
        h("h3", null, ui("legacy.preview")),
        renderPreviews(item.urls),
        h("div", { class: "links small" },
          item.model ? [h("a", { href: item.model, download: `${item.name}.glb` }, "model.glb"), " · "] : null,
          item.log ? h("a", { href: item.log, target: "_blank" }, "build.log") : null),
      ) : null,
      r?.log_tail?.length ? h("details", null, h("summary", { class: "small" }, ui("stats.log")), h("pre", { class: "log" }, r.log_tail.join("\n"))) : null,
    );
  };

  const loadModel = async () => {
    panel.setCaption(item.name);
    if (item.model) await panel.show(item.model, {});
    else {
      await panel.show(null, {});
      panel.setStatus(item.state === "queued" || item.state === "running" ? ui("material.renderQueued") : item.state === "failed" ? ui("legacy.openError") : ui("legacy.notRendered"));
    }
  };

  const rebuild = async () => {
    await api.legacyRebuild(item.id);
    item = await api.legacyItem(id);
    drawSide();
  };

  const copyPath = async () => {
    const path = item.files[item.format];
    try {
      await navigator.clipboard.writeText(path);
      toast(ui("legacy.pathCopied"), "ok");
    } catch {
      toast(path);
    }
  };

  mount(root, h("section", { class: "page page-entity" },
    h("div", { class: "entity-head" },
      h("div", null,
        h("div", { class: "crumbs" }, h("a", { href: "#/legacy" }, "Legacy"), " / ", item.source, item.folder ? ` / ${item.folder}` : ""),
        h("h1", null, item.name, h("span", { class: "chips head-chip" }, item.formats.map((f) => h("span", { class: "chip chip-socket" }, `.${f}`)))),
      ),
      h("div", { class: "btn-group" },
        h("a", { class: `btn${prev ? "" : " disabled"}`, href: prev ? `#/legacy/${prev}` : undefined, title: ui("legacy.previous") }, "←"),
        h("span", { class: "muted small" }, pos >= 0 ? `${pos + 1} / ${lastOrder.length}` : ""),
        h("a", { class: `btn${next ? "" : " disabled"}`, href: next ? `#/legacy/${next}` : undefined, title: ui("legacy.next") }, "→"),
      ),
    ),
    h("div", { class: "entity-layout legacy-layout" }, center, side),
  ));
  drawSide();
  await loadModel();

  const off = onBuildEvent(async (ev) => {
    if (ev.type !== "legacy" || ev.item !== id || (ev.state !== "ok" && ev.state !== "failed")) return;
    item = await api.legacyItem(id);
    drawSide();
    await loadModel();
  });
  const onTheme = () => panel.applyTheme();
  window.addEventListener("themechange", onTheme);
  return () => {
    off();
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("themechange", onTheme);
    panel.dispose();
  };
}

function stat(label: string, value: unknown): HTMLElement[] | null {
  if (value === null || value === undefined || value === "") return null;
  return [h("dt", null, label), h("dd", null, String(value))];
}
