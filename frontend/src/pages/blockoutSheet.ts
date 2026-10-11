import { entityTitle, ui } from "../i18n";
// One shared viewport for a kit's components, with the same layout available in Blender.

import { api, blockoutSheetHref, type BlockoutSheet, type BlockoutSheetMember } from "../api";
import { h, mount, toast } from "../dom";
import { onBuildEvent } from "../events";
import { ViewerPanel } from "../viewerPanel";
import { PROJECTION_KEYS, renderPreviews } from "../previews";

const STATE_LABEL: Record<string, string> = {
  none: ui("build.need"), queued: ui("status.queued"), running: ui("status.running"), ok: ui("build.need"),
  failed: ui("build.failure"), invalid: ui("build.recipeFailure"),
};

export async function renderBlockoutSheet(root: HTMLElement, id: string, query: URLSearchParams): Promise<() => void> {
  const context: { asset?: string; v?: string } = {};
  if (query.get("asset")) context.asset = query.get("asset")!;
  if (query.get("v")) context.v = query.get("v")!;
  let sheet: BlockoutSheet | null = null;
  let panel: ViewerPanel | null = null;
  let disposed = false;
  let loading = false;
  let busy: "build" | "blender" | "projections" | null = null;
  let loadVersion = 0;
  let shownLayout = "";
  let refreshPending = false;
  let refreshTimer = 0;
  let error = "";
  let notice = "";
  let deferredFocus: string | undefined;

  const title = h("h1", null, ui("blockout.title"));
  const subtitle = h("p", { class: "muted small" }, ui("blockout.intro"));
  const actions = h("div", { class: "btn-group blockout-actions" });
  const feedback = h("div", { class: "blockout-feedback", "aria-live": "polite" });
  const assetLinks = h("div", { class: "blockout-assets" });
  const summary = h("div", { class: "blockout-summary small", role: "status", "aria-live": "polite" });
  const assemblyHelp = h("p", { class: "muted small" });
  const stage = h("section", { class: "blockout-stage", "aria-label": ui("blockout.table") },
    h("div", { class: "blockout-placeholder", role: "status" }, ui("blockout.loading")));
  const list = h("div", { class: "blockout-parts" });
  const projections = h("section", { class: "section blockout-projections", "aria-label": ui("blockout.projections") });
  const page = h("section", { class: "page blockout-page" },
    h("div", { class: "entity-head" },
      h("div", null, h("div", { class: "crumbs" }, h("a", { href: "#/components" }, ui("nav.components")), ui("blockout.breadcrumb")),
        title, subtitle), actions),
    assetLinks, feedback, summary, assemblyHelp,
    h("div", { class: "blockout-layout" }, stage,
      h("aside", { class: "pane blockout-sidebar", "aria-label": ui("blockout.components") },
        h("h2", null, ui("meta.details")), list)), projections,
  );
  mount(root, page);

  const ready = (member: BlockoutSheetMember) => Boolean(member.model || member.url);
  const runnable = (member: BlockoutSheetMember) => !ready(member)
    && member.build_state !== "invalid" && member.build_state !== "queued" && member.build_state !== "running";
  const restoreFocus = (key: string | undefined) => {
    if (!key) return;
    const element = [...page.querySelectorAll<HTMLElement>("[data-sheet-control]")]
      .find((element) => element.dataset.sheetControl === key);
    if (!element || (element as HTMLButtonElement).disabled) return;
    element.focus({ preventScroll: true });
    deferredFocus = undefined;
  };

  const draw = () => {
    if (disposed) return;
    const focused = page.contains(document.activeElement)
      ? (document.activeElement as HTMLElement).dataset.sheetControl
      : document.activeElement === document.body ? deferredFocus : undefined;
    deferredFocus = focused;
    const members = sheet?.members ?? [];
    const missing = members.filter((member) => !ready(member));
    const buildable = members.filter(runnable);
    const queued = missing.filter((member) => member.build_state === "queued" || member.build_state === "running");
    const disabled = Boolean(busy || loading || !sheet);
    const sheetTitle = sheet?.group_id.startsWith("asset:")
      ? entityTitle({ id: sheet.context?.id ?? sheet.group_id.slice("asset:".length), title: sheet.title })
      : sheet?.title;
    title.textContent = sheetTitle ? ui("dynamic.sheetTitle", { title: sheetTitle }) : ui("blockout.title");
    subtitle.textContent = sheet?.context
      ? ui("dynamic.sheetAsset", { id: sheet.context.id, vid: sheet.context.vid })
      : ui("blockout.chooseAssetHelp");
    mount(actions,
      h("button", { class: "btn", type: "button", disabled: Boolean(busy || loading),
        "data-sheet-control": "refresh", onClick: () => void load() }, loading ? ui("common.loading") : ui("common.refresh")),
      missing.length ? h("button", { class: "btn", type: "button", disabled: disabled || !buildable.length,
        "data-sheet-control": "build", onClick: () => void buildMissing() },
      busy === "build" ? ui("blockout.queueing") : buildable.length ? ui("dynamic.buildParts", { count: buildable.length }) : queued.length ? ui("blockout.building") : ui("blockout.unavailable")) : null,
      h("button", { class: "btn btn-primary", type: "button", disabled: disabled || !members.length || Boolean(missing.length),
        "data-sheet-control": "blender", onClick: () => void openBlender() }, busy === "blender" ? ui("blockout.preparing") : ui("blockout.openBlender")),
      h("button", { class: "btn", type: "button", disabled: disabled || !members.length || Boolean(missing.length),
        "data-sheet-control": "projections", onClick: () => {
          if (PROJECTION_KEYS.every((key) => sheet?.previews?.[key])) projections.scrollIntoView({ behavior: "smooth", block: "start" });
          else void mutate("projections");
        } }, busy === "projections" ? ui("blockout.snapshots") : PROJECTION_KEYS.every((key) => sheet?.previews?.[key]) ? ui("projections.title") : ui("projections.create")),
      sheet?.blend.available && sheet.blend.url
        ? h("a", { class: "btn", href: sheet.blend.url, download: "blockout-sheet.blend", "data-sheet-control": "download" }, ui("blockout.download")) : null,
    );
    mount(feedback,
      error ? h("div", { class: "box box-error small", role: "alert" }, error) : null,
      notice ? h("div", { class: "box box-info small" }, notice) : null,
      sheet && missing.length ? h("p", { class: "muted small" }, ui("blockout.buildFirst")) : null,
    );
    summary.textContent = sheet
      ? ui("dynamic.readyParts", { ready: members.length - missing.length, total: members.length }) + (queued.length ? ui("dynamic.queueSuffix", { count: queued.length }) : "")
      : loading ? ui("blockout.loadingParts") : ui("blockout.partsUnavailable");
    assemblyHelp.textContent = sheet
      ? ui("dynamic.sheetBlenderHelp", { grid: sheet.snap_grid })
      : "";
    mount(assetLinks, sheet?.context ? h("a", { class: "btn btn-sm", href: `#/assets/${encodeURIComponent(sheet.context.id)}?v=${encodeURIComponent(sheet.context.vid)}` },
      `← ${sheet.context.id} · ${sheet.context.vid}`) : null,
      sheet && sheet.related_assets.length > 0 ? h("div", { class: "btn-group" },
        h("span", { class: "muted small" }, ui("blockout.assetsLabel")), sheet.related_assets.map((asset) => h("a", {
          class: "btn btn-sm" + (sheet!.context?.id === asset.id ? " btn-toggle active" : ""),
          href: blockoutSheetHref(id, asset.id), "data-sheet-control": `asset:${asset.id}`,
        }, entityTitle(asset)))) : null);
    mount(list, sheet ? members.length ? members.map((member) => h("article", { class: "blockout-part" },
      member.preview ? h("img", { src: member.preview, alt: "", loading: "lazy", width: 56, height: 56 })
        : h("span", { class: "blockout-part-empty", "aria-hidden": "true" }, "◇"),
      h("div", { class: "blockout-part-text" },
        h("a", { href: `#/components/${encodeURIComponent(member.id)}${member.vid ? `?v=${encodeURIComponent(member.vid)}` : ""}`,
          "data-sheet-control": `part:${member.ref || `components/${member.id}`}` }, h("strong", null, entityTitle(member))),
        h("span", { class: "mono muted small" }, `${member.id} · ${member.vid || ui("blockout.noVariant")}`),
        h("span", { class: "small" + (member.error ? " error" : " muted") },
          ready(member) ? ui("common.ready") : STATE_LABEL[member.build_state] ?? ui("build.need")),
        member.source_slots.length > 1 ? h("span", { class: "muted small" }, ui("dynamic.partReuse", { count: member.source_slots.length })) : null,
        member.error ? h("span", { class: "error small" }, member.error) : null,
      ))) : h("p", { class: "muted small" }, ui("blockout.empty"))
      : h("p", { class: "muted small" }, loading ? ui("common.loading") : ui("blockout.retry")));
    mount(projections, sheet && Object.keys(sheet.previews ?? {}).length ? [
      h("h2", null, ui("blockout.views")),
      h("p", { class: "muted small" }, ui("blockout.viewHelp")),
      renderPreviews(sheet.previews!),
    ] : null);
    if (!panel && !loading) mount(stage, h("div", { class: "blockout-placeholder" },
      sheet ? ui("blockout.noModels") : ui("blockout.retryParts")));
    restoreFocus(focused);
  };

  const showSheet = async (data: BlockoutSheet, version: number) => {
    if (disposed || version !== loadVersion || !root.isConnected) return;
    sheet = data;
    if (!panel) {
      panel = new ViewerPanel("", { materialSelect: false });
      mount(stage, panel.el);
    }
    draw();
    const items = data.members.filter(ready).map((member) => ({
      url: (member.model || member.url)!,
      label: member.label && member.label !== member.title ? member.label : entityTitle(member),
      ref: member.ref || `components/${member.id}`, position: member.position,
    }));
    const signature = JSON.stringify([items, data.snap_grid]);
    if (signature === shownLayout) return;
    const shown = await panel.showLayout(items, { gridSize: null, voxelSize: data.snap_grid, preset: "iso", animate: false });
    if (disposed || version !== loadVersion) return;
    if (shown || !items.length) shownLayout = signature;
  };

  const scheduleRefresh = () => {
    if (disposed) return;
    if (loading || busy) { refreshPending = true; return; }
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(() => { refreshTimer = 0; void load(); }, 350);
  };

  const load = async () => {
    if (disposed || busy) return;
    if (loading) { refreshPending = true; return; }
    const version = ++loadVersion;
    loading = true;
    error = "";
    draw();
    try {
      const data = await api.blockoutSheet(id, context);
      if (disposed || version !== loadVersion) return;
      await showSheet(data, version);
    } catch (err) {
      if (disposed || version !== loadVersion) return;
      error = err instanceof Error ? err.message : ui("blockout.error");
    } finally {
      if (!disposed && version === loadVersion) {
        loading = false;
        draw();
        if (refreshPending) { refreshPending = false; scheduleRefresh(); }
      }
    }
  };

  const mutate = async (action: "build" | "blender" | "projections") => {
    if (disposed || busy || loading || !sheet) return;
    if (action !== "build" && (!sheet.members.length || sheet.members.some((member) => !ready(member)))) return;
    if (action === "build" && !sheet.members.some(runnable)) return;
    const version = ++loadVersion;
    window.clearTimeout(refreshTimer);
    busy = action;
    error = "";
    notice = "";
    draw();
    try {
      if (action === "build") {
        const result = await api.buildBlockoutSheet(id, context);
        if (disposed || version !== loadVersion) return;
        const failures = result.submitted.filter((entry) => entry.error);
        notice = failures.length ? ui("dynamic.sheetQueueError", { error: failures.map((entry) => entry.error).join("; ") })
          : result.submitted.length ? ui("blockout.queuedNotice") : ui("blockout.allBuilt");
        await showSheet(result.sheet, version);
      } else {
        const result = action === "projections" ? await api.blockoutSheetProjections(id, context) : await api.openBlockoutSheet(id, context);
        if (disposed || version !== loadVersion) return;
        const data = { ...result.sheet, blend: { url: result.blend.url, available: true } };
        notice = action === "projections" ? ui("blockout.readyNotice")
          : result.blender?.state === "error"
          ? ui("dynamic.sheetOpenError", { error: result.blender.error || ui("common.retryAction") })
          : result.blender?.state === "already_open" ? ui("blockout.alreadyOpen")
            : result.blender?.state === "opened" ? ui("blockout.openNotice") : ui("blockout.prepared");
        await showSheet(data, version);
      }
    } catch (err) {
      if (!disposed && version === loadVersion) {
        error = err instanceof Error ? err.message : ui("blockout.actionError");
        toast(error, "error");
      }
    } finally {
      if (!disposed && version === loadVersion) {
        busy = null;
        draw();
        if (refreshPending) { refreshPending = false; scheduleRefresh(); }
      }
    }
  };
  const buildMissing = () => mutate("build");
  const openBlender = () => mutate("blender");

  const offEvents = onBuildEvent((event) => {
    if (disposed || !sheet) return;
    if (sheet.members.some((member) => event.hash && member.hash === event.hash
      || event.kind === "components" && event.id === member.id)
      || event.kind === "assets" && event.id === sheet.context?.id) scheduleRefresh();
  });
  const onTheme = () => panel?.applyTheme();
  window.addEventListener("themechange", onTheme);
  void load();
  return () => {
    disposed = true;
    loadVersion++;
    window.clearTimeout(refreshTimer);
    offEvents();
    window.removeEventListener("themechange", onTheme);
    panel?.dispose();
  };
}
