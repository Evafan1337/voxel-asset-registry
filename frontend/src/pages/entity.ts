import { entityTitle, parameterLabel, ui } from "../i18n";
// Entity page: variant tree (left), 3D viewer or side-by-side compare (center), variant panel (right).

import { api, ApiError, blockoutSheetHref, KIND_LABEL, type EntityDoc, type Kind, type Report, type Status, type Tree, type VariantDetail } from "../api";
import { openBranchForm } from "../branchForm";
import { debounce, fmtValue, h, mount, stars, statusBadge, toast } from "../dom";
import { onBuildEvent } from "../events";
import { renderTree } from "../tree";
import type { ModelMeta } from "../viewer";
import { ViewerPanel } from "../viewerPanel";
import { PROJECTION_KEYS, renderPreviews } from "../previews";

export async function renderEntity(root: HTMLElement, kind: Kind, id: string, query: URLSearchParams): Promise<() => void> {
  const [entity, initialTree, catalogGroups, sheetDiscovery] = await Promise.all([
    api.entity(kind, id), api.tree(kind, id),
    kind === "assets" ? api.catalogGroups().catch(() => null) : Promise.resolve(null),
    kind === "assets" ? api.assetBlockoutSheets(id, query.get("v")).catch(() => null) : Promise.resolve(null),
  ]);
  let tree: Tree = initialTree;
  let selected: string | null = query.get("v") ?? pickDefault(tree);
  let compare: string | null = query.get("cmp");
  let detail: VariantDetail | null = null;
  let compareDetail: VariantDetail | null = null;
  let disposed = false;
  let selectedVersion = 0;
  let compareVersion = 0;
  let treeVersion = 0;
  let patchVersion = 0;
  let rebuildBusy = false;
  const loadedUrl = new Map<ViewerPanel, string | null>();
  const modelVersions = new Map<ViewerPanel, number>();
  const run = (task: Promise<unknown>) => void task.catch((err: Error) => {
    if (!disposed) toast(err.message, "error");
  });

  const meta: ModelMeta = { gridSize: entity.interface?.grid_size ?? null, voxelSize: entity.interface?.voxel_size ?? 0.25,
    ...(kind === "characters" ? { preset: "34" as const, clip: "idle" } : {}) };

  const treePane = h("aside", { class: "pane tree-pane" });
  const center = h("section", { class: "pane center-pane" });
  const side = h("aside", { class: "pane side-pane" });
  const docDrawer = h("div", { class: "doc-drawer", hidden: true },
    h("div", { class: "row-between" },
      h("strong", null, ui("entity.docResolved")),
      h("span", { class: "muted small" }, ui("entity.llmContext"))),
    h("pre", { class: "markdown" }, entity.markdown));
  const sheetLinks = h("span", { class: "btn-group entity-sheet-links" });
  const sheetGroups = sheetDiscovery?.groups.filter((group) => group.component_count > 0)
    ?? catalogGroups?.groups.filter((group) => group.items.includes(`assets/${id}`)
      && group.items.some((item) => item.startsWith("components/"))) ?? [];
  const drawSheetLinks = () => {
    if (kind !== "assets") return;
    const groups = sheetGroups.length ? sheetGroups : [{ id: `asset:${id}`, title: entity.title || id }];
    if (groups.length > 3) {
      mount(sheetLinks, h("select", { "aria-label": ui("blockout.groupHint"), onChange: (event: Event) => {
        const groupId = (event.target as HTMLSelectElement).value;
        if (groupId) location.hash = blockoutSheetHref(groupId, id, selected);
      } }, h("option", { value: "", selected: true }, ui("blockout.loadingLink")),
      groups.map((group) => h("option", { value: group.id }, group.title))));
      return;
    }
    mount(sheetLinks, groups.map((group) => h("a", {
      class: "btn", href: blockoutSheetHref(group.id, id, selected),
      title: ui("dynamic.tableHint", { title: entityTitle(entity) }),
    }, groups.length === 1 ? ui("blockout.title") : ui("dynamic.sheetLink", { title: group.title }))));
  };
  drawSheetLinks();

  mount(root, h("section", { class: "page page-entity" },
    header(entity, kind, () => { docDrawer.hidden = !docDrawer.hidden; }, () => selected, kind === "assets" ? sheetLinks : null),
    docDrawer,
    h("div", { class: "entity-layout" }, treePane, center, side),
  ));

  const mainPanel = new ViewerPanel();
  let comparePanel: ViewerPanel | null = null;
  const diffBox = h("div", { class: "diff-box" });

  // ------------------------------------------------------------------ url / selection
  const syncUrl = () => {
    const params = new URLSearchParams();
    if (selected) params.set("v", selected);
    if (compare) params.set("cmp", compare);
    history.replaceState(null, "", `#/${kind}/${id}${params.toString() ? `?${params}` : ""}`);
    drawSheetLinks();
  };

  const select = (vid: string, shift: boolean) => {
    if (shift && selected && vid !== selected) {
      compare = compare === vid ? null : vid;
    } else {
      selected = vid;
      if (compare === vid) compare = null;
      detail = null;
      mount(side, h("p", { class: "muted", role: "status" }, ui("entity.loadingVariant")));
      mainPanel.setStatus(ui("entity.loadingVariant"));
    }
    syncUrl();
    drawTree();
    run(loadSelected(true));
    run(layoutCenter());
  };

  const drawTree = () => {
    if (disposed) return;
    const focusedVariant = treePane.contains(document.activeElement)
      ? (document.activeElement as HTMLElement).dataset.variant : null;
    mount(treePane,
      h("div", { class: "pane-head" }, h("strong", null, ui("entity.variants")), h("span", { class: "muted small" }, ui("material.compareHint"))),
      tree.nodes.length ? renderTree(tree.nodes, { selected, compare, onSelect: select }) : h("p", { class: "muted" }, ui("entity.noVariants")),
    );
    if (focusedVariant) treePane.querySelector<HTMLElement>(`[data-variant="${CSS.escape(focusedVariant)}"]`)?.focus();
  };

  // ------------------------------------------------------------------ center
  const layoutCenter = async () => {
    if (compare && selected) {
      if (!comparePanel) {
        comparePanel = new ViewerPanel();
        const a = mainPanel;
        const b = comparePanel;
        a.viewer.onCameraChange = () => b.viewer.copyCameraFrom(a.viewer);
        b.viewer.onCameraChange = () => a.viewer.copyCameraFrom(b.viewer);
        a.onOptionChange = (k, v) => b.setOption(k, v);
        b.onOptionChange = (k, v) => a.setOption(k, v);
      }
      mainPanel.setCaption(`A · ${selected}`);
      comparePanel.setCaption(`B · ${compare}`);
      mount(center,
        h("div", { class: "pane-head" },
          h("strong", null, ui("dynamic.compare", { a: selected ?? "", b: compare ?? "" })),
          h("span", { class: "muted small" }, ui("viewer.synced")),
          h("button", { class: "btn btn-sm", onClick: closeCompare }, ui("material.closeCompare"))),
        h("div", { class: "compare-grid" }, mainPanel.el, comparePanel.el),
        diffBox,
      );
      await loadCompare();
    } else {
      if (comparePanel) {
        comparePanel.dispose();
        loadedUrl.delete(comparePanel);
        comparePanel = null;
        mainPanel.viewer.onCameraChange = null;
        mainPanel.onOptionChange = null;
      }
      mainPanel.setCaption(selected ? `${id}@${selected}` : "");
      mount(center, mainPanel.el);
    }
  };

  const closeCompare = () => {
    compare = null;
    syncUrl();
    drawTree();
    run(layoutCenter());
  };

  const showModel = async (panel: ViewerPanel, d: VariantDetail | null) => {
    if (disposed) return;
    const version = (modelVersions.get(panel) ?? 0) + 1;
    modelVersions.set(panel, version);
    const busy = d?.build_state === "queued" || d?.build_state === "running";
    const url = d?.urls?.model ?? null;
    if (loadedUrl.get(panel) === url && url) {
      panel.setStatus(busy ? ui("build.rebuilding") : "");
      return;
    }
    loadedUrl.delete(panel);
    if (!url) {
      await panel.show(null, meta);
      if (!disposed && modelVersions.get(panel) === version) {
        panel.setStatus(busy ? ui("build.queued") : d?.errors.length ? ui("build.invalid") : ui("build.noModel"));
      }
      return;
    }
    const shown = await panel.show(url, meta);
    if (!shown || disposed || modelVersions.get(panel) !== version) return;
    loadedUrl.set(panel, url);
    if (busy) panel.setStatus(ui("build.rebuilding"));
  };

  const loadCompare = async () => {
    if (!compare || !selected || !comparePanel) return;
    const version = ++compareVersion;
    const selectedId = selected;
    const compareId = compare;
    const panel = comparePanel;
    const [d, diff] = await Promise.all([
      api.variant(kind, id, compareId),
      api.diff(`${kind}/${id}/${selectedId}`, `${kind}/${id}/${compareId}`).catch(() => null),
    ]);
    if (disposed || version !== compareVersion || compareId !== compare || selectedId !== selected || panel !== comparePanel) return;
    compareDetail = d;
    await showModel(panel, compareDetail);
    if (disposed || version !== compareVersion || panel !== comparePanel) return;
    panel.viewer.copyCameraFrom(mainPanel.viewer);
    let onlyChanged = true;
    const drawDiff = () => {
      if (!diff) {
        mount(diffBox, h("p", { class: "muted" }, ui("entity.diffUnavailable")));
        return;
      }
      const rows = diff.rows.filter((r) => !onlyChanged || r.changed);
      mount(diffBox,
        h("div", { class: "row-between" },
          h("strong", null, ui("dynamic.diff", { count: diff.changed })),
          h("label", { class: "small" }, h("input", { type: "checkbox", checked: onlyChanged, onChange: () => { onlyChanged = !onlyChanged; drawDiff(); } }), ui("entity.onlyDifferences"))),
        h("table", { class: "table diff-table" },
          h("thead", null, h("tr", null, h("th", null, ui("entity.parameter")), h("th", null, `A · ${selected}`), h("th", null, `B · ${compare}`))),
          h("tbody", null, rows.map((r) => h("tr", { class: r.changed ? "changed" : "" },
            h("td", { class: "mono" }, r.key), h("td", null, fmtValue(r.a)), h("td", null, fmtValue(r.b))))),
        ),
        h("div", { class: "muted small mono" }, `hash A ${diff.a.hash} · hash B ${diff.b.hash}${diff.a.hash === diff.b.hash ? ui("entity.sameArtifact") : ""}`),
      );
    };
    drawDiff();
  };

  // ------------------------------------------------------------------ side panel
  const loadSelected = async (reloadModel: boolean) => {
    const version = ++selectedVersion;
    const vid = selected;
    if (!selected) {
      mount(side, h("p", { class: "muted" }, ui("entity.selectVariant")));
      await showModel(mainPanel, null);
      return;
    }
    const next = await api.variant(kind, id, selected);
    if (disposed || version !== selectedVersion || vid !== selected) return;
    detail = next;
    renderSide();
    if (reloadModel) await showModel(mainPanel, detail);
  };

  const patch = async (body: Parameters<typeof api.patch>[3]) => {
    if (!detail) return;
    const vid = detail.id;
    const version = ++patchVersion;
    try {
      const next = await api.patch(kind, id, vid, body);
      if (disposed) return;
      if (selected === vid && version === patchVersion) { detail = next; renderSide(); }
      await refreshTree();
    } catch (err) {
      toast((err as Error).message, "error");
    }
  };

  const renderSide = () => {
    if (disposed) return;
    const d = detail;
    if (!d) return;
    const v = d.variant;
    const buildOk = d.build_state === "ok";

    const note = h("textarea", { rows: 2, value: v.note, placeholder: ui("common.note") });
    note.addEventListener("change", () => void patch({ note: note.value }));

    const tagInput = h("input", { type: "text", placeholder: ui("core.addTag"), class: "tag-input" });
    tagInput.addEventListener("keydown", (ev: KeyboardEvent) => {
      if (ev.key === "Enter" && tagInput.value.trim()) void patch({ tags: [...v.tags, tagInput.value.trim()] });
    });

    const nextStatusAfterUnset: Status = buildOk ? "built" : d.build_state === "failed" ? "failed" : "draft";
    const ownBlend = d.source?.own && v.status !== "approved" && v.status !== "archived";
    mount(side,
      h("div", { class: "pane-head" },
        h("h2", null, v.id), statusBadge(v.status, d.build_state),
        h("span", { class: "chip chip-level" }, `L${v.level}`),
        v.author === "llm" ? h("span", { class: "chip chip-llm" }, "llm") : null,
      ),
      h("div", { class: "muted small mono" },
        d.hash ? `hash ${d.hash}` : "hash —", v.parent ? ` · parent ${v.parent}` : ui("entity.root"),
        d.chain ? ui("dynamic.chain", { chain: d.chain.join(" → ") }) : ""),

      h("div", { class: "actions" },
        h("button", { class: "btn btn-primary", disabled: d.errors.length > 0, onClick: () => branch() }, ui("entity.branch")),
        h("button", { class: "btn", disabled: rebuildBusy || d.build_state === "queued" || d.build_state === "running",
          onClick: () => void rebuild() }, rebuildBusy ? ui("build.sending") : ui("build.rebuild")),
        h("button", { class: "btn", disabled: rebuildBusy || d.errors.length > 0 || d.build_state === "queued" || d.build_state === "running",
          title: ui("projections.tooltip"),
          onClick: () => {
            if (d.urls && PROJECTION_KEYS.every((key) => d.urls![key])) side.querySelector(".projection-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
            else void rebuild();
          } }, d.urls && PROJECTION_KEYS.every((key) => d.urls![key]) ? ui("projections.title") : ui("projections.create")),
        v.status === "approved"
          ? h("button", { class: "btn", onClick: () => void patch({ status: nextStatusAfterUnset }) }, ui("entity.unapprove"))
          : h("button", { class: "btn btn-ok", disabled: !buildOk, title: buildOk ? "" : ui("build.successFirst"), onClick: () => void patch({ status: "approved" }) }, ui("entity.approve")),
        v.status === "archived"
          ? h("button", { class: "btn", onClick: () => void patch({ status: nextStatusAfterUnset }) }, ui("entity.unarchive"))
          : h("button", { class: "btn btn-ghost", onClick: () => void patch({ status: "archived" }) }, ui("entity.archive")),
      ),
      kind === "components" || kind === "assets" ? h("div", { class: "actions" },
        h("button", {
          class: "btn", disabled: d.errors.length > 0 || blenderBusy,
          title: kind === "assets"
            ? ui("blender.forkAssetHelp")
            : ui("blender.forkComponentHelp"),
          onClick: () => void openBlender(true),
        }, ui("entity.forkBlender")),
        ownBlend ? h("button", {
          class: "btn", disabled: blenderBusy,
          title: d.source?.open ? ui("entity.blenderAlready") : ui("dynamic.blendContinue", { file: d.source?.file ?? "" }),
          onClick: () => void openBlender(false),
        }, d.source?.open ? ui("entity.openedBlender") : ui("blockout.openBlender")) : null,
      ) : null,
      d.source ? h("div", { class: "box box-info small" },
        ui("dynamic.manualGeometry", { file: d.source.file + (d.source.own ? "" : ` (${d.source.variant})`) }),
        kind === "assets" ? ui("entity.manualSlots") : ui("entity.manualParams"),
        ui("entity.blenderSaveHelp")) : null,

      h("div", { class: "field" }, h("span", { class: "field-label" }, ui("entity.rating")), stars(v.rating, (r) => void patch({ rating: r }))),
      h("div", { class: "field" }, h("span", { class: "field-label" }, ui("common.note")), note),
      h("div", { class: "field" }, h("span", { class: "field-label" }, ui("tags.title")),
        h("div", { class: "chips" },
          v.tags.map((t) => h("span", { class: "chip" }, t,
            h("button", { class: "chip-x", title: ui("common.remove"), onClick: () => void patch({ tags: v.tags.filter((x) => x !== t) }) }, "×"))),
          tagInput)),

      d.errors.length ? h("div", { class: "box box-error" }, h("strong", null, ui("build.invalid")), d.errors.map((e) => h("div", { class: "small" }, e))) : null,
      kind === "assets" ? slotsSection(d) : null,
      paramsSection(d, entity),
      kind === "characters" ? clipsSection(d, entity) : null,
      reportSection(d, () => void rebuild(), rebuildBusy),
      socketsSection(entity, d),
    );
  };

  const branch = () => {
    if (!detail) return;
    if (kind === "assets") {
      location.hash = `#/assets/${id}/compose?parent=${detail.id}`;
      return;
    }
    openBranchForm(entity, detail, async (vid) => {
      toast(ui("dynamic.created", { ref: vid }), "ok");
      await refreshTree();
      select(vid, false);
    });
  };

  let blenderBusy = false;
  const openBlender = async (fork: boolean) => {
    if (!detail || blenderBusy) return;
    blenderBusy = true;
    renderSide();
    if (fork) toast(ui("dynamic.blendPreparing", { ref: detail.id }), "info");
    try {
      const res = await api.openInBlender(kind, id, detail.id, { fork });
      const session = res.blender;
      if (session?.state === "error") toast(ui("dynamic.blendError", { ref: res.id, error: session.error ?? "" }), "error");
      else toast(session?.state === "already_open" ? ui("dynamic.blendAlready", { ref: res.id }) : ui("dynamic.blendOpen", { ref: res.id }), "ok");
      await refreshTree();
      if (fork) select(res.id, false);
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      blenderBusy = false;
      renderSide();
    }
  };

  const rebuild = async () => {
    if (!detail || rebuildBusy) return;
    const vid = detail.id;
    rebuildBusy = true;
    renderSide();
    try {
      const res = await api.rebuild(kind, id, vid);
      if (disposed) return;
      toast(res.state === "invalid" ? ui("dynamic.cannotBuild", { error: res.error ?? "" }) : ui("dynamic.rebuild", { ref: vid, state: res.state }), res.state === "invalid" ? "error" : "info");
      await refreshTree();
      await loadSelected(false);
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      rebuildBusy = false;
      renderSide();
    }
  };

  const refreshTree = async () => {
    const version = ++treeVersion;
    const next = await api.tree(kind, id);
    if (disposed || version !== treeVersion) return;
    tree = next;
    drawTree();
  };

  // ------------------------------------------------------------------ events
  const onKey = (ev: KeyboardEvent) => {
    if (ev.key === "Escape" && compare && !document.querySelector(".modal-backdrop")) closeCompare();
  };
  document.addEventListener("keydown", onKey);

  const refreshAll = debounce(() => {
    const vids = new Set(touched);
    touched.clear();
    const refreshMetadata = metadataDirty;
    metadataDirty = false;
    run((async () => {
      const [, updatedEntity] = await Promise.all([
        refreshTree(), refreshMetadata ? api.entity(kind, id) : Promise.resolve(null),
      ]);
      if (disposed) return;
      if (updatedEntity) {
        Object.assign(entity, updatedEntity);
        const description = docDrawer.querySelector("pre");
        if (description) description.textContent = updatedEntity.markdown;
      }
      if (selected && vids.has(selected)) await loadSelected(true);
      if (compare && vids.has(compare) && comparePanel) await loadCompare();
    })());
  }, 250);
  const touched = new Set<string>();
  let metadataDirty = false;
  const offEvents = onBuildEvent((ev) => {
    if (ev.kind !== kind || ev.id !== id) return;
    if (ev.type === "entity") {
      metadataDirty = true;
      if (selected) touched.add(selected);
      if (compare) touched.add(compare);
      refreshAll();
      return;
    }
    if (!ev.vid) return;
    touched.add(ev.vid);
    if (ev.type === "build" && (ev.state === "ok" || ev.state === "failed") && !ev.cached) {
      toast(`${ev.vid}: ${ev.state === "ok" ? ui("core.builtCheck") : ui("dynamic.buildFailed", { error: ev.error ?? "" })}`, ev.state === "ok" ? "ok" : "error");
    }
    refreshAll();
  });

  const onTheme = () => {
    mainPanel.applyTheme();
    comparePanel?.applyTheme();
  };
  window.addEventListener("themechange", onTheme);

  const dispose = () => {
    disposed = true;
    refreshAll.cancel();
    offEvents();
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("themechange", onTheme);
    mainPanel.dispose();
    comparePanel?.dispose();
  };
  try {
    drawTree();
    await layoutCenter();
    await loadSelected(true);
    return dispose;
  } catch (err) {
    dispose();
    throw err;
  }
}

function pickDefault(tree: Tree): string | null {
  const approved = tree.nodes.filter((n) => n.status === "approved");
  const pick = approved[approved.length - 1] ?? tree.nodes[tree.nodes.length - 1];
  return pick?.id ?? null;
}

function header(entity: EntityDoc, kind: Kind, toggleDoc: () => void, currentVariant: () => string | null,
                sheetLinks: HTMLElement | null): HTMLElement {
  return h("div", { class: "entity-head" },
    h("div", null,
      h("div", { class: "crumbs" }, h("a", { href: `#/${kind}` }, KIND_LABEL[kind]), " / ", h("span", { class: "mono" }, entity.id)),
      h("h1", null, entityTitle(entity),
        entity.kind === "components" && entity.type === "structure" ? h("span", { class: "chip chip-structure head-chip" }, ui("entity.structure")) : null),
      h("div", { class: "muted small" },
        entity.chain.length > 1 ? h("span", { class: "mono" }, ui("dynamic.inheritance", { chain: entity.chain.join(" → ") })) : ui("entity.noInheritance"),
        ` · generator_version ${entity.generator_version}`,
        entity.interface ? ` · grid ${entity.interface.grid_size.join("×")} × ${entity.interface.voxel_size} m` : "",
        entity.category ? ` · ${entity.category}` : "",
        entity.interface?.mounts.length ? ui("dynamic.mounts", { mounts: entity.interface.mounts.join(", ") }) : ""),
    ),
    h("div", { class: "btn-group" },
      h("button", { class: "btn", onClick: toggleDoc }, ui("common.description")),
      sheetLinks,
      kind === "assets" ? h("a", { class: "btn btn-primary", href: `#/assets/${entity.id}/compose` }, ui("entity.compose")) : null,
      kind === "characters" ? h("a", { class: "btn btn-primary", href: "#/characters/cast" }, ui("core.cast")) : null,
      kind === "assets" ? h("button", { class: "btn", onClick: () => { const vid = currentVariant(); if (vid) location.hash = `#/assets/${entity.id}/edit?parent=${vid}`; } }, ui("entity.edit")) : null,
    ),
  );
}

const PARAM_GROUPS: Record<string, string> = {
  body: ui("entity.body"), proportions: ui("experimental.proportions"), head: ui("experimental.head"), hair: ui("experimental.hair"), outfit: ui("experimental.outfit"), palette: ui("experimental.palette"),
};

function paramsSection(d: VariantDetail, entity: EntityDoc): HTMLElement | null {
  const params = d.params ?? {};
  const names = Object.keys(entity.params);
  if (!names.length) return null;
  const changed = new Set(d.changed ?? []);
  const row = (name: string) => {
    const source = d.sources?.[name] ?? "default";
    return h("tr", { class: changed.has(name) ? "changed" : "", title: entity.params[name].description },
      h("td", { class: "mono" }, parameterLabel(name)),
      h("td", null, fmtValue(params[name])),
      h("td", { class: "muted small" }, source === "default" ? ui("common.default") : ui("dynamic.from", { source })));
  };
  const groups = [...new Set(names.map((n) => entity.params[n].group ?? ""))];
  const grouped = groups.length > 1 || groups[0] !== "";
  return h("div", { class: "section" },
    h("h3", null, ui("entity.params"), h("span", { class: "muted small" }, ui("entity.changedHint"))),
    h("table", { class: "table" },
      h("tbody", null, grouped
        ? groups.flatMap((g) => [
          h("tr", { class: "param-group" }, h("td", { colspan: 3 }, PARAM_GROUPS[g] ?? (g || ui("entity.other")))),
          ...names.filter((n) => (entity.params[n].group ?? "") === g).map(row)])
        : names.map(row)),
    ),
  );
}

function clipsSection(d: VariantDetail, entity: EntityDoc): HTMLElement {
  const declared = entity.character?.clips ?? [];
  const built = new Map((d.report?.stats?.animations ?? []).map((a) => [a.name, a]));
  return h("div", { class: "section" },
    h("h3", null, ui("core.animations"), h("span", { class: "muted small" }, ui("experimental.sharedRig", { rig: entity.character?.rig ?? "?" }))),
    h("div", { class: "chips" }, declared.map((c) => {
      const a = built.get(c);
      return h("span", { class: `chip ${a ? "chip-ok" : "chip-missing"}`, title: a ? ui("experimental.frameCount", { count: a.frames[1] }) : ui("core.clipMissing") },
        a ? ui("experimental.clipDuration", { clip: c, seconds: a.seconds ?? a.frames[1] / 24 }) : ui("experimental.clipAbsent", { clip: c }));
    })),
  );
}

function slotsSection(d: VariantDetail): HTMLElement | null {
  if (!d.slots) return null;
  return h("div", { class: "section" },
    h("h3", null, ui("entity.slots")),
    h("table", { class: "table" },
      h("tbody", null, d.slots.map((s) => h("tr", { class: s.changed ? "changed" : "" },
        h("td", { class: "mono" }, s.name, s.socket ? h("div", { class: "muted small" }, `→ ${s.socket}`) : h("div", { class: "muted small" }, ui("entity.body"))),
        h("td", null, s.ref && s.component
          ? h("a", { href: `#/components/${s.component}?v=${s.variant}` }, s.ref)
          : h("span", { class: "muted" }, ui("common.empty"))),
        h("td", { class: "muted small" }, s.source === "default" ? "" : ui("dynamic.from", { source: s.source })),
      ))),
    ),
    d.slots.filter((s) => s.params).map((s) => h("details", { class: "slot-params" },
      h("summary", { class: "small" }, ui("dynamic.slotParams", { name: s.name, ref: s.ref ?? "" })),
      h("table", { class: "table table-compact" }, h("tbody", null,
        Object.entries(s.params ?? {}).map(([k, val]) => h("tr", null, h("td", { class: "mono" }, k), h("td", null, fmtValue(val)))))),
    )),
  );
}

function socketsSection(entity: EntityDoc, d: VariantDetail): HTMLElement | null {
  const sockets = entity.interface?.sockets ?? [];
  if (!sockets.length) return null;
  const used = new Set((d.slots ?? []).filter((s) => s.ref && s.socket && !s.socket.includes(".")).map((s) => s.socket));
  return h("div", { class: "section" },
    h("h3", null, ui("entity.sockets"), h("span", { class: "muted small" },
      entity.kind === "assets" ? ui("entity.freeSockets") : ui("entity.socketInterface"))),
    h("table", { class: "table" }, h("tbody", null, sockets.map((s) => h("tr", { class: used.has(s.name) ? "muted" : "" },
      h("td", { class: "mono" }, s.name),
      h("td", null, h("span", { class: `chip chip-socket` }, s.type)),
      h("td", { class: "muted small" }, used.has(s.name) ? ui("entity.socketOccupied") : s.description))))),
  );
}

function reportSection(d: VariantDetail, generateProjections?: () => void, pending = false): HTMLElement {
  const r: Report | null | undefined = d.report;
  const busy = d.build_state === "queued" || d.build_state === "running";
  if (!r) {
    return h("div", { class: "section" }, h("h3", null, ui("entity.build")),
      h("p", { class: "muted" }, busy ? ui("build.queued") : ui("build.never")));
  }
  const s = r.stats ?? {};
  return h("div", { class: "section" },
    h("h3", null, "Build report ",
      h("span", { class: `badge ${r.status === "ok" ? "badge-built" : "badge-failed"}` }, r.status === "ok" ? "ok" : "failed"),
      busy ? h("span", { class: "badge badge-busy" }, ui("build.rebuilding")) : null),
    r.error ? h("div", { class: "box box-error small" }, r.error) : null,
    h("ul", { class: "checks" }, (r.checks ?? []).map((c) =>
      h("li", { class: c.ok ? "pass" : "fail" }, h("span", { class: "check-mark" }, c.ok ? "✓" : "✗"),
        h("strong", null, c.name), h("span", { class: "small" }, c.message)))),
    semanticReport(r),
    d.urls ? h("div", { class: "projection-section" },
      h("h3", null, ui("projections.section")),
      h("p", { class: "small muted" }, ui("projections.help")),
      PROJECTION_KEYS.some((key) => !d.urls![key]) && generateProjections
        ? h("button", { class: "btn btn-sm", disabled: busy || pending, onClick: generateProjections },
          busy || pending ? ui("projections.loading") : ui("projections.create")) : null,
      renderPreviews(d.kind === "characters" ? { ...d.urls, preview_iso: undefined } : d.urls)) : null,
    h("dl", { class: "stats" },
      stat(ui("stats.polygons"), s.faces !== undefined ? `${s.faces} (${s.tris} tris)` : null),
      stat(ui("stats.vertices"), s.verts),
      stat(ui("stats.boundsM"), s.bbox_m?.join(" × ")),
      stat(ui("stats.boundsVox"), s.bbox_vox?.join(" × ")),
      stat(ui("viewer.sockets"), s.sockets?.map((x) => x.name).join(", ") || "—"),
      stat(ui("viewer.animation"), s.animations?.map((a) => `${a.name}: ${a.seconds ?? a.frames[1] / 24} s${a.nodes !== undefined ? `, nodes ${a.nodes}` : ""}`).join(", ") || "—"),
      stat(ui("stats.duration"), r.duration_s !== undefined ? `${r.duration_s} s` : null),
      stat(ui("status.built"), r.built_at?.replace("T", " ").replace("+00:00", " UTC")),
    ),
    d.urls ? h("div", { class: "links small" },
      h("a", { href: d.urls.model, download: `${d.entity_id}_${d.id}.glb` }, "model.glb"), " · ",
      h("a", { href: d.urls.report, target: "_blank" }, "report.json"), " · ",
      h("a", { href: d.urls.log, target: "_blank" }, "build.log")) : null,
    r.log_tail?.length ? h("details", null, h("summary", { class: "small" }, ui("stats.log")), h("pre", { class: "log" }, r.log_tail.join("\n"))) : null,
  );
}

function semanticReport(r: Report): HTMLElement | null {
  const structure = r.structure;
  const composition = r.composition;
  if ((!structure || structure.status === "skipped") && !composition) return null;
  return h("div", { class: "semantic-report" },
    structure && structure.status !== "skipped" ? h("div", { class: "semantic-card" },
      h("strong", null, ui("dynamic.structure", { status: structure.status === "ok" ? ui("entity.verified") : ui("status.failed") })),
      structure.purpose ? h("p", { class: "small" }, structure.purpose) : null,
      h("p", { class: "small muted" },
        ui("dynamic.relationships", { verified: structure.verified?.length ?? 0, issues: structure.issues?.length ?? 0 }) +
        Object.entries(structure.parts ?? {}).map(([part, count]) => `${part} ×${count}`).join(", ")),
      structure.issues?.length ? h("ul", { class: "semantic-issues" }, structure.issues.map((issue) =>
        h("li", null, `${issue.type}: ${issue.message} (${issue.objects.join(", ")})`))) : null,
    ) : null,
    composition ? h("div", { class: "semantic-card" },
      h("strong", null, ui("entity.compositionVerified")),
      h("p", { class: "small" }, composition.read_at_glance),
      h("p", { class: "small" }, ui("dynamic.primaryMass", { mass: composition.primary_mass, hero: composition.hero_feature })),
      h("p", { class: "small muted" },
        ui("dynamic.secondary", { parts: composition.secondary_features.join(", ") || "—", zones: composition.quiet_zones.join(", ") || "—" })),
      h("p", { class: "small muted" },
        ui("dynamic.density", { parts: composition.metrics.large_attachments, roof: Math.round(composition.metrics.roof_density * 100), front: Math.round(composition.metrics.front_density * 100), free: Math.round(composition.metrics.empty_socket_ratio * 100) })),
    ) : null,
  );
}

function stat(label: string, value: unknown): HTMLElement[] | null {
  if (value === null || value === undefined) return null;
  return [h("dt", null, label), h("dd", null, String(value))];
}
