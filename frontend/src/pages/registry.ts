import { entityTitle, LOCALES, renderText, ui } from "../i18n";
// Registry page: entity catalog with tag filters and UI-only groups.

import "./registryGroups.css";

import { api, blockoutSheetHref, KIND_LABEL, type CatalogGroup, type EntitySummary, type Kind } from "../api";
import { h, mount, STATUS_LABEL, toast } from "../dom";
import { onBuildEvent } from "../events";

interface Filters {
  tags: Set<string>;
  level: number | null;
  query: string;
  group: string;
  expandedTags: boolean;
}

const KINDS: Kind[] = ["components", "assets", "materials", "characters"];
const filters = Object.fromEntries(KINDS.map((kind) => [kind, {
  tags: new Set<string>(), level: null, query: "", group: "*", expandedTags: false,
}])) as Record<Kind, Filters>;
type ViewMode = "cards" | "list";
const VIEW_KEY = "var.catalog.view.";

function storedView(kind: Kind): ViewMode {
  if (kind !== "components" && kind !== "assets") return "cards";
  try {
    const saved = localStorage.getItem(VIEW_KEY + kind);
    if (saved === "cards" || saved === "list") return saved;
  } catch { /* storage unavailable */ }
  return "list";
}

export async function renderRegistry(root: HTMLElement, kind: Kind): Promise<() => void> {
  const f = filters[kind];
  const canChangeView = kind === "components" || kind === "assets";
  let viewMode = storedView(kind);
  const grid = h("div", { class: "registry-groups" });
  const filterBar = h("div", { class: "filter-bar" });
  const viewSwitch = h("div", { class: "registry-view-switch", role: "group", "aria-label": ui("catalog.view") });
  const resultCount = h("span", { class: "muted small", role: "status", "aria-live": "polite", "aria-atomic": "true" });
  const resetButton = h("button", { class: "btn btn-sm", type: "button", onClick: () => resetFilters() }, ui("catalog.reset"));
  const searchInput = h("input", {
    type: "search", value: f.query, placeholder: ui("catalog.searchPlaceholder"), "aria-label": ui("catalog.search"),
    onInput: () => {
      f.query = searchInput.value;
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => draw(), 100);
    },
  });
  const settingsPanel = h("div", { class: "registry-settings-panel", hidden: true });
  const groupsPanel = h("div", { class: "registry-settings-panel registry-groups-panel", hidden: true });
  const counts = Object.fromEntries(KINDS.map((k) => [k, h("span", { class: "tab-count" })])) as Record<Kind, HTMLElement>;
  const abstractNote = h("p", { class: "muted small" });

  const page = h("section", { class: "page page-registry" },
      h("div", { class: "tabs" },
        KINDS.map((k) =>
          h("a", { class: "tab" + (k === kind ? " active" : ""), href: "#/" + k, "aria-current": k === kind ? "page" : undefined }, KIND_LABEL[k], counts[k])),
        h("a", { class: "tab nav-legacy", href: "#/legacy", title: ui("legacy.hint") }, "Legacy"),
      ),
      h("div", { class: "registry-search-row" }, searchInput,
        h("div", { class: "registry-results" }, resultCount, resetButton, canChangeView ? viewSwitch : null)),
      filterBar,
      settingsPanel,
      groupsPanel,
      grid,
      abstractNote,
  );
  mount(root, page);

  let items: EntitySummary[] = [];
  const catalogs = new Map<Kind, EntitySummary[]>();
  let entities: EntitySummary[] = [];
  let allTags: string[] = [];
  const searchable = new Map<EntitySummary, string>();
  const entityTags = new Map<EntitySummary, Set<string>>();
  const cachedCards = new WeakMap<EntitySummary, Partial<Record<ViewMode, HTMLElement>>>();
  const groupIndex = new Map<string, string>();
  let disposed = false;
  let catalogGeneration = 0;
  let managerOpening = false;
  let searchTimer = 0;
  let allKnownTags: string[] = [];
  let priorityTags: string[] = [];
  let settingsAvailable = true;
  let draftTags: string[] = [];
  let editing = false;
  let saving = false;
  let editorError = "";
  let groups: CatalogGroup[] = [];
  let groupsAvailable = true;
  let organizing = false;
  let groupSaving = false;
  let groupError = "";
  let newGroupId = "";
  let newGroupTitle = "";

  const indexGroups = () => {
    groupIndex.clear();
    for (const group of groups) for (const item of group.items) {
      // Keep the first assignment if an older settings file contains duplicates.
      if (!groupIndex.has(item)) groupIndex.set(item, group.id);
    }
    if (f.group !== "*" && f.group !== "" && !groups.some((group) => group.id === f.group)) f.group = "*";
  };
  const groupOf = (entity: EntitySummary): string => groupIndex.get(`${entity.kind}/${entity.id}`) ?? "";
  const indexItems = () => {
    entities = items.filter((entity) => !entity.abstract);
    searchable.clear();
    entityTags.clear();
    for (const entity of entities) {
      const tags = new Set([...entity.tags, ...entity.variant_tags]);
      entityTags.set(entity, tags);
      searchable.set(entity, [entity.id, entity.title, ...LOCALES.map((locale) => renderText(entityTitle(entity), locale)), entity.category, entity.inherits, ...tags].filter(Boolean).join(" ").toLocaleLowerCase());
    }
    allTags = [...new Set(entities.flatMap((entity) => [...entityTags.get(entity)!]))].sort();
    for (const tag of f.tags) if (!allTags.includes(tag)) f.tags.delete(tag);
    abstractNote.textContent = items.some((entity) => entity.abstract)
      ? ui("catalog.abstractBases") + items.filter((entity) => entity.abstract).map((entity) => entity.id).join(", ") : "";
  };
  const resetFilters = () => {
    window.clearTimeout(searchTimer);
    f.tags.clear();
    f.level = null;
    f.query = "";
    f.group = "*";
    searchInput.value = "";
    draw();
    searchInput.focus();
  };

  const persistGroups = async (next: CatalogGroup[]) => {
    groupSaving = true;
    groupError = "";
    draw();
    drawGroupsEditor();
    try {
      groups = (await api.saveCatalogGroups(next)).groups;
      indexGroups();
      toast(ui("catalog.groupsSaved"), "ok");
    } catch (error) {
      groupError = error instanceof Error ? error.message : ui("catalog.groupsError");
    } finally {
      groupSaving = false;
      draw();
      drawGroupsEditor();
    }
  };

  const assignGroup = (entity: EntitySummary, groupId: string) => {
    const item = `${entity.kind}/${entity.id}`;
    const next = groups.map((group) => ({
      ...group,
      items: group.items.filter((entry) => entry !== item),
    }));
    next.find((group) => group.id === groupId)?.items.push(item);
    void persistGroups(next);
  };

  const groupCard = (entity: EntitySummary) => {
    let modes = cachedCards.get(entity);
    if (!modes) { modes = {}; cachedCards.set(entity, modes); }
    let entityCard = modes[viewMode];
    if (!entityCard) {
      entityCard = viewMode === "list" ? listRow(entity) : card(entity);
      modes[viewMode] = entityCard;
    }
    return h("div", { class: "registry-card-wrap" },
    entityCard,
    organizing ? h("label", { class: "registry-card-group" }, ui("catalog.group"),
      h("select", {
        disabled: groupSaving,
        value: groupOf(entity),
        "data-registry-control": `assign:${entity.kind}/${entity.id}`,
        onChange: (ev: Event) => assignGroup(entity, (ev.target as HTMLSelectElement).value),
      },
        h("option", { value: "", selected: !groupOf(entity) }, ui("catalog.ungrouped")),
        groups.map((group) => h("option", { value: group.id, selected: groupOf(entity) === group.id }, group.title)),
      ),
    ) : null,
    );
  };

  const draw = () => {
    if (disposed || !page.isConnected) return;
    const focusedControl = page.contains(document.activeElement)
      ? (document.activeElement as HTMLElement).dataset.registryControl : undefined;
    const words = f.query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const selectedTags = [...f.tags];
    const visible = entities.filter((entity) =>
      (f.level === null || entity.complexity_level === f.level)
      && selectedTags.every((tag) => entityTags.get(entity)!.has(tag))
      && (f.group === "*" || groupOf(entity) === f.group)
      && words.every((word) => searchable.get(entity)!.includes(word)));
    resultCount.textContent = ui("dynamic.catalogCount", { shown: visible.length, total: entities.length });
    resetButton.hidden = !f.tags.size && f.level === null && f.group === "*" && !f.query;
    if (canChangeView) mount(viewSwitch, (["list", "cards"] as const).map((mode) => h("button", {
      type: "button", class: "btn btn-sm btn-toggle" + (viewMode === mode ? " active" : ""),
      "aria-pressed": String(viewMode === mode), "data-registry-control": `view:${mode}`,
      onClick: () => {
        viewMode = mode;
        try { localStorage.setItem(VIEW_KEY + kind, mode); } catch { /* storage unavailable */ }
        draw();
      },
    }, mode === "list" ? ui("catalog.list") : ui("catalog.cards"))));
    const availableTags = new Set(allTags);
    const pinnedTags = [...new Set(priorityTags)].filter((t) => availableTags.has(t));
    const pinnedSet = new Set(pinnedTags);
    const otherTags = allTags.filter((t) => !pinnedSet.has(t));
    const compactTags = otherTags.filter((tag, index) => index < 12 || f.tags.has(tag));
    const shownTags = f.expandedTags ? otherTags : compactTags;
    const tagChip = (t: string, priority = false) => h("button", {
      class: "chip chip-toggle" + (priority ? " chip-priority" : "") + (f.tags.has(t) ? " active" : ""),
      type: "button", "aria-pressed": String(f.tags.has(t)), "data-registry-control": `tag:${t}`,
      onClick: () => { f.tags.has(t) ? f.tags.delete(t) : f.tags.add(t); draw(); },
    }, t);

    mount(filterBar,
      h("div", { class: "tag-groups" },
        pinnedTags.length ? h("div", { class: "tag-row tag-row-priority" },
          h("span", { class: "tag-row-label muted small" }, ui("catalog.importantLabel")),
          h("div", { class: "chips" }, pinnedTags.map((t) => tagChip(t, true))),
        ) : null,
        otherTags.length || !pinnedTags.length ? h("div", { class: "tag-row" },
          h("span", { class: "tag-row-label muted small" }, pinnedTags.length ? ui("catalog.otherLabel") : ui("catalog.tagsLabel")),
          h("div", { class: "chips" }, shownTags.map((t) => tagChip(t)),
            otherTags.length > 12 && (f.expandedTags || otherTags.length > compactTags.length) ? h("button", {
              class: "btn btn-sm registry-more-tags", type: "button", "aria-expanded": String(f.expandedTags),
              "data-registry-control": "more-tags", onClick: () => { f.expandedTags = !f.expandedTags; draw(); },
            }, f.expandedTags ? ui("catalog.collapseTags") : ui("dynamic.moreTags", { count: otherTags.length - compactTags.length })) : null),
        ) : null,
        f.tags.size > 1 ? h("span", { class: "muted small" }, ui("catalog.matchAll")) : null,
      ),
      h("div", { class: "registry-filter-actions" },
        kind !== "materials" && groupsAvailable ? h("label", { class: "level-filter" }, h("span", { class: "muted small" }, ui("catalog.groupLabel")),
          h("select", { "data-registry-control": "group", onChange: (ev: Event) => { f.group = (ev.target as HTMLSelectElement).value; draw(); } },
            h("option", { value: "*", selected: f.group === "*" }, ui("common.all")),
            h("option", { value: "", selected: f.group === "" }, ui("catalog.ungrouped")),
            groups.map((group) => h("option", { value: group.id, selected: f.group === group.id }, group.title)),
          ),
        ) : null,
        h("label", { class: "level-filter" }, h("span", { class: "muted small" }, ui("catalog.levelLabel")),
          h("select", {
            "data-registry-control": "level",
            onChange: (ev: Event) => {
              const v = (ev.target as HTMLSelectElement).value;
              f.level = v === "" ? null : Number(v);
              draw();
            },
          },
            h("option", { value: "", selected: f.level === null }, ui("common.any")),
            [0, 1, 2, 3].map((l) => h("option", { value: l, selected: f.level === l }, "L" + l + " — " + LEVEL_NAMES[l])),
          ),
        ),
        h("button", {
          class: "btn btn-sm" + (editing ? " btn-toggle active" : ""),
          type: "button",
          "aria-expanded": String(editing), "data-registry-control": "settings",
          disabled: saving || !settingsAvailable,
          onClick: () => {
            if (saving || !settingsAvailable) return;
            editing = !editing;
            if (editing) { draftTags = [...priorityTags]; editorError = ""; }
            draw();
            drawEditor();
          },
        }, editing ? ui("catalog.closeSettings") : ui("catalog.configureTags")),
        !settingsAvailable ? h("span", { class: "muted small" }, ui("catalog.tagSettingsUnavailable")) : null,
        canChangeView ? h("button", {
          class: "btn btn-sm", type: "button", disabled: managerOpening, "data-registry-control": "tag-manager",
          onClick: () => void manageTags(),
        }, ui("tags.manage")) : null,
        kind !== "materials" && groupsAvailable ? h("button", {
          class: "btn btn-sm" + (organizing ? " btn-toggle active" : ""), type: "button", disabled: groupSaving,
          "aria-expanded": String(organizing), "data-registry-control": "groups",
          onClick: () => { organizing = !organizing; draw(); drawGroupsEditor(); },
        }, organizing ? ui("catalog.closeGroups") : ui("catalog.manageGroups")) : null,
        kind !== "materials" && !groupsAvailable ? h("span", { class: "muted small" }, ui("catalog.groupsUnavailable")) : null,
        kind === "assets" ? h("a", { class: "btn btn-primary btn-sm", href: "#/assets/new" }, ui("catalog.addAsset")) : null,
        kind === "characters" ? h("a", { class: "btn btn-primary btn-sm", href: "#/characters/cast" }, ui("core.castTogether")) : null,
        kind === "characters" ? h("a", { class: "btn btn-sm", href: "#/characters/lab", title: ui("experimental.catalogHint") }, "Reference Lab") : null,
      ),
    );

    const byGroup = new Map<string, EntitySummary[]>();
    for (const entity of visible) {
      const groupId = groupOf(entity);
      if (!byGroup.has(groupId)) byGroup.set(groupId, []);
      byGroup.get(groupId)!.push(entity);
    }
    const sections = [...groups, { id: "", title: ui("catalog.ungrouped") }]
      .map((group) => ({ ...group, entities: byGroup.get(group.id) ?? [] })).filter((section) => section.entities.length);
    mount(grid, sections.length ? sections.map((section) => h("section", { class: "registry-group" },
      h("div", { class: "registry-group-head" },
        h("h2", null, section.title), h("span", { class: "muted small" }, ui("dynamic.items", { count: section.entities.length })),
        section.id && groups.find((group) => group.id === section.id)?.items.some((item) => item.startsWith("components/"))
          ? h("a", { class: "btn btn-sm registry-sheet-link", href: blockoutSheetHref(section.id) }, ui("catalog.table")) : null),
      viewMode === "list" ? h("div", { class: "registry-list-head", "aria-hidden": "true" },
        h("span", null, ui("catalog.preview")), h("span", null, ui("common.name")), h("span", null, "ID"), h("span", null, ui("tags.title")), h("span", null, ui("catalog.type"))) : null,
      h("div", { class: viewMode === "list" ? "registry-list" : "card-grid" }, section.entities.map(groupCard)),
    )) : h("div", { class: "registry-empty" },
      h("strong", null, entities.length ? ui("common.noResults") : ui("catalog.empty")),
      entities.length ? h("p", { class: "muted small" }, ui("catalog.tryFilters")) : null,
      entities.length ? h("button", { class: "btn", type: "button", onClick: resetFilters }, ui("catalog.reset")) : null));
    if (focusedControl) [...page.querySelectorAll<HTMLElement>("[data-registry-control]")]
      .find((element) => element.dataset.registryControl === focusedControl)?.focus({ preventScroll: true });
  };

  const drawEditor = () => {
    settingsPanel.hidden = !editing;
    if (!editing) return;

    const input = h("input", {
      type: "text",
      list: "registry-known-tags",
      placeholder: ui("catalog.tagPlaceholder"),
      "aria-label": ui("catalog.addPriority"),
      disabled: saving,
    });
    const addTag = () => {
      if (saving) return;
      const tag = input.value.trim();
      if (!tag || draftTags.includes(tag)) return;
      draftTags.push(tag);
      editorError = "";
      drawEditor();
      settingsPanel.querySelector<HTMLInputElement>(".priority-add input")?.focus();
    };
    input.addEventListener("keydown", (ev: KeyboardEvent) => {
      if (ev.key === "Enter") { ev.preventDefault(); addTag(); }
    });
    const moveTag = (index: number, offset: number) => {
      const other = index + offset;
      [draftTags[index], draftTags[other]] = [draftTags[other], draftTags[index]];
      drawEditor();
    };
    const save = async () => {
      saving = true;
      editorError = "";
      draw();
      drawEditor();
      try {
        const settings = await api.saveRegistrySettings(draftTags);
        priorityTags = settings.priority_tags;
        editing = false;
        draw();
        toast(ui("catalog.tagsSaved"), "ok");
      } catch (error) {
        editorError = error instanceof Error ? error.message : ui("catalog.settingsError");
      } finally {
        saving = false;
        draw();
        drawEditor();
      }
    };

    mount(settingsPanel,
      h("div", { class: "row-between" },
        h("strong", null, ui("catalog.priority")),
        h("span", { class: "muted small" }, ui("catalog.allSections")),
      ),
      h("p", { class: "muted small" }, ui("catalog.tagOrderHelp")),
      h("div", { class: "priority-list" },
        draftTags.length ? draftTags.map((tag, index) =>
          h("div", { class: "priority-item" },
            h("span", { class: "priority-name mono" }, tag),
            h("button", { class: "btn btn-sm", type: "button", title: ui("common.up"), "aria-label": ui("catalog.moveUp") + tag, disabled: saving || index === 0, onClick: () => moveTag(index, -1) }, "↑"),
            h("button", { class: "btn btn-sm", type: "button", title: ui("common.down"), "aria-label": ui("catalog.moveDown") + tag, disabled: saving || index === draftTags.length - 1, onClick: () => moveTag(index, 1) }, "↓"),
            h("button", { class: "btn btn-sm", type: "button", title: ui("common.remove"), "aria-label": ui("common.remove") + " " + tag, disabled: saving, onClick: () => { draftTags.splice(index, 1); drawEditor(); } }, "×"),
          ),
        ) : h("p", { class: "muted small" }, ui("catalog.emptyTagList")),
      ),
      h("div", { class: "priority-add" },
        input,
        h("datalist", { id: "registry-known-tags" }, allKnownTags.filter((t) => !draftTags.includes(t)).map((t) => h("option", { value: t }))),
        h("button", { class: "btn btn-sm", type: "button", disabled: saving, onClick: addTag }, ui("common.add")),
      ),
      editorError ? h("p", { class: "error small", role: "alert" }, editorError) : null,
      h("div", { class: "priority-actions" },
        h("button", { class: "btn btn-primary", type: "button", disabled: saving, onClick: () => void save() }, saving ? ui("common.saving") : ui("common.save")),
        h("button", { class: "btn", type: "button", disabled: saving, onClick: () => { editing = false; draw(); drawEditor(); } }, ui("common.cancel")),
      ),
    );
  };

  const drawGroupsEditor = () => {
    groupsPanel.hidden = !organizing;
    if (!organizing) return;
    const idInput = h("input", { type: "text", value: newGroupId, placeholder: "building_parts", "aria-label": ui("catalog.groupId"), disabled: groupSaving,
      onInput: (ev: Event) => { newGroupId = (ev.target as HTMLInputElement).value; } });
    const titleInput = h("input", { type: "text", value: newGroupTitle, placeholder: ui("catalog.groupName"), "aria-label": ui("catalog.newGroupName"), disabled: groupSaving,
      onInput: (ev: Event) => { newGroupTitle = (ev.target as HTMLInputElement).value; } });
    const add = () => {
      const id = idInput.value.trim();
      const title = titleInput.value.trim();
      if (!ID_RE.test(id)) { groupError = ui("catalog.invalidGroupId"); drawGroupsEditor(); return; }
      if (!title) { groupError = ui("catalog.needGroupName"); drawGroupsEditor(); return; }
      if (groups.some((group) => group.id === id)) { groupError = ui("dynamic.groupExists", { id }); drawGroupsEditor(); return; }
      void persistGroups([...groups, { id, title, items: [] }]).then(() => {
        if (groupError) return;
        newGroupId = "";
        newGroupTitle = "";
        drawGroupsEditor();
      });
    };
    for (const input of [idInput, titleInput]) input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); if (!groupSaving) add(); }
    });
    mount(groupsPanel,
      h("div", { class: "row-between" }, h("strong", null, ui("catalog.logicalGroups")),
        h("span", { class: "muted small" }, ui("catalog.orderOnly"))),
      h("p", { class: "muted small" }, ui("catalog.groupHelp")),
      h("div", { class: "registry-group-list" }, groups.map((group) => h("div", { class: "registry-group-item" },
        h("span", { class: "mono" }, group.id),
        h("input", { type: "text", value: group.title, disabled: groupSaving, "aria-label": ui("dynamic.groupName", { id: group.id }),
          onChange: (ev: Event) => {
            const title = (ev.target as HTMLInputElement).value.trim();
            if (!title) { groupError = ui("catalog.emptyGroupName"); drawGroupsEditor(); return; }
            void persistGroups(groups.map((entry) => entry.id === group.id ? { ...entry, title } : entry));
          },
        }),
        h("span", { class: "muted small" }, String(group.items.length)),
        h("button", { class: "btn btn-sm", type: "button", disabled: groupSaving, title: ui("dynamic.deleteGroup", { name: group.title }), "aria-label": ui("dynamic.deleteGroup", { name: group.title }),
          onClick: () => void persistGroups(groups.filter((entry) => entry.id !== group.id)),
        }, "×"),
      ))),
      h("div", { class: "registry-group-add" }, idInput, titleInput,
        h("button", { class: "btn btn-sm", type: "button", disabled: groupSaving, onClick: add }, ui("catalog.addGroup"))),
      groupError ? h("p", { class: "error small", role: "alert" }, groupError) : null,
    );
  };

  const updateCatalog = (loadedKind: Kind, list: EntitySummary[]) => {
    catalogs.set(loadedKind, list);
    counts[loadedKind].textContent = String(list.filter((entity) => !entity.abstract).length);
    counts[loadedKind].removeAttribute("title");
    allKnownTags = [...new Set([...catalogs.values()].flatMap((list) =>
      list.filter((e) => !e.abstract).flatMap((e) => [...e.tags, ...e.variant_tags])))].sort();
    if (loadedKind === kind) { items = list; indexItems(); }
  };
  const manageTags = async () => {
    if (managerOpening || disposed) return;
    managerOpening = true;
    draw();
    try {
      const { openTagManager } = await import("../tagManager");
      if (disposed || !page.isConnected) return;
      await openTagManager(async ({ old_name, name }: { old_name: string; name: string | null }) => {
        for (const changedKind of ["components", "assets"] as const) {
          const state = filters[changedKind];
          if (state.tags.delete(old_name) && name) state.tags.add(name);
        }
        if (editing) draftTags = [...new Set(draftTags.map((tag) => tag === old_name ? name : tag).filter((tag): tag is string => tag !== null))];
        if (!disposed && page.isConnected) await load();
      });
    } catch (error) {
      if (!disposed && page.isConnected) toast(error instanceof Error ? error.message : ui("catalog.managerError"), "error");
    } finally { managerOpening = false; draw(); }
  };
  const load = async () => {
    const generation = ++catalogGeneration;
    const [settings, loadedGroups, lists] = await Promise.all([
      api.registrySettings().then((settings) => { if (generation === catalogGeneration) settingsAvailable = true; return settings; })
        .catch(() => { if (generation === catalogGeneration) settingsAvailable = false; return { priority_tags: [] }; }),
      api.catalogGroups().then((groups) => { if (generation === catalogGeneration) groupsAvailable = true; return groups; })
        .catch(() => { if (generation === catalogGeneration) groupsAvailable = false; return { groups: [] as CatalogGroup[] }; }),
      Promise.allSettled(KINDS.map((loadedKind) => api.list(loadedKind))),
    ]);
    if (disposed || !page.isConnected || generation !== catalogGeneration) return;
    const current = lists[KINDS.indexOf(kind)];
    if (current.status === "rejected") throw current.reason;
    groups = loadedGroups.groups;
    indexGroups();
    priorityTags = settings.priority_tags;
    lists.forEach((result, index) => {
      if (result.status === "fulfilled") updateCatalog(KINDS[index], result.value);
      else { counts[KINDS[index]].textContent = "—"; counts[KINDS[index]].title = ui("catalog.sectionError"); }
    });
    draw();
    if (editing) drawEditor();
    if (organizing) drawGroupsEditor();
  };

  await load();
  if (!page.isConnected) return () => { disposed = true; };
  let timer = 0;
  let refreshing = false;
  const pendingKinds = new Set<Kind>();
  const refresh = async () => {
    if (disposed || refreshing || !pendingKinds.size) return;
    refreshing = true;
    const changedKinds = [...pendingKinds];
    const generation = catalogGeneration;
    pendingKinds.clear();
    try {
      const results = await Promise.allSettled(changedKinds.map((changedKind) => api.list(changedKind)));
      if (disposed || !page.isConnected || generation !== catalogGeneration) return;
      let failed = false;
      results.forEach((result, index) => {
        if (result.status === "fulfilled") updateCatalog(changedKinds[index], result.value);
        else failed = true;
      });
      if (changedKinds.includes(kind)) draw();
      if (failed) toast(ui("catalog.staleError"), "error");
    } finally {
      refreshing = false;
      if (!disposed && pendingKinds.size) timer = window.setTimeout(() => void refresh(), 400);
    }
  };
  const unsubscribe = onBuildEvent((ev) => {
    if (ev.type === "legacy") return;
    if (ev.state === "ok" || ev.state === "failed" || ev.state === "updated" || ev.state === "created") {
      pendingKinds.add(ev.kind ?? kind);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void refresh(), 400);
    }
  });
  return () => {
    disposed = true;
    window.clearTimeout(timer);
    window.clearTimeout(searchTimer);
    pendingKinds.clear();
    unsubscribe();
  };
}

const ID_RE = /^[a-z][a-z0-9_]*$/;
const LEVEL_NAMES = [ui("meta.blockout"), ui("meta.silhouette"), ui("meta.details"), ui("viewer.animation")];

function previewImage(entity: EntitySummary): HTMLElement {
  return entity.preview?.url ? h("img", {
    src: entity.preview.url, alt: entityTitle(entity), loading: "lazy", decoding: "async", width: 320, height: 320,
    onError: (ev: Event) => (ev.target as HTMLImageElement).replaceWith(h("div", { class: "thumb-empty" }, ui("core.unavailablePreview"))),
  }) : h("div", { class: "thumb-empty" }, ui("common.noPreview"));
}

function listRow(entity: EntitySummary): HTMLElement {
  const tags = [...new Set([...entity.tags, ...entity.variant_tags])];
  return h("a", { class: "card registry-list-row", href: `#/${entity.kind}/${entity.id}`, "data-registry-control": `card:${entity.kind}/${entity.id}` },
    h("div", { class: "registry-list-thumb" }, previewImage(entity)),
    h("div", { class: "registry-list-title" },
      h("strong", null, entityTitle(entity)),
      h("span", { class: "muted small" }, `${entity.variant_count} ${variantWord(entity.variant_count)}`),
      entity.error ? h("span", { class: "error small registry-card-error", title: entity.error }, entity.error) : null),
    h("div", { class: "registry-list-id mono small", "data-label": "ID" }, entity.id,
      entity.inherits ? h("span", { class: "muted" }, `← ${entity.inherits}`) : null),
    h("div", { class: "chips registry-list-tags", "data-label": ui("tags.title") }, tags.length ? tags.map((tag) => h("span", {
      class: "chip" + (entity.tags.includes(tag) ? "" : " chip-variant"), title: entity.tags.includes(tag) ? undefined : ui("core.tagVariant"),
    }, tag)) : h("span", { class: "muted small" }, ui("core.noTags"))),
    h("div", { class: "registry-list-type", "data-label": ui("catalog.type") },
      h("span", { class: "chip" + (entity.type === "structure" ? " chip-structure" : "") }, entity.type === "structure" ? ui("entity.structure") : ui("entity.part")),
      h("span", { class: "chip chip-level", title: LEVEL_NAMES[entity.complexity_level] ?? ui("meta.levelHint") }, `L${entity.complexity_level}`)),
  );
}

function card(e: EntitySummary): HTMLElement {
  const counts = Object.entries(e.status_counts)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([s, n]) => h("span", { class: `mini-status st-${s}`, title: STATUS_LABEL[s] ?? s }, `${n} ${STATUS_LABEL[s] ?? s}`));
  const tags = [...new Set([...e.tags, ...e.variant_tags])];
  return h("a", { class: "card", href: `#/${e.kind}/${e.id}`, "data-registry-control": `card:${e.kind}/${e.id}` },
    h("div", { class: "card-thumb" },
      previewImage(e),
      e.preview ? h("span", { class: `badge badge-${e.preview.status} card-badge` }, e.preview.vid) : null,
    ),
    h("div", { class: "card-body" },
      h("div", { class: "row-between" },
        h("strong", { class: "registry-card-title" }, entityTitle(e)),
        h("span", { class: "chips" },
          e.type === "structure" ? h("span", { class: "chip chip-structure", title: ui("meta.structureHint") }, ui("entity.structure")) : null,
          e.kind === "materials" ? h("span", { class: "chip chip-structure", title: ui("meta.materialShader") }, ui("meta.shader")) : null,
          e.character?.rig ? h("span", { class: "chip chip-structure", title: ui("core.sharedSkeleton") }, ui("core.rig")) : null,
          h("span", { class: "chip chip-level", title: LEVEL_NAMES[e.complexity_level] ?? ui("meta.levelHint") }, `L${e.complexity_level}`)),
      ),
      h("div", { class: "muted small mono" }, e.id, e.inherits ? ` ← ${e.inherits}` : ""),
      h("div", { class: "card-counts" }, h("span", null, `${e.variant_count} ${variantWord(e.variant_count)}`), counts),
      e.character ? h("div", { class: "muted small" },
        ui("experimental.clipCount", { rig: e.character.rig ?? ui("core.noRig"), built: e.character.built_clips.length || 0, total: e.character.clips.length }),
        e.character.polys ? ui("experimental.faceCount", { count: e.character.polys }) : "") : null,
      h("div", { class: "chips registry-card-tags" }, tags.slice(0, 6).map((tag) => h("span", {
        class: "chip" + (e.tags.includes(tag) ? "" : " chip-variant"), title: e.tags.includes(tag) ? undefined : ui("core.tagVariant"),
      }, tag)), tags.length > 6 ? h("span", { class: "chip", title: tags.slice(6).join(", "), "aria-label": ui("catalog.otherTags") + tags.slice(6).join(", ") }, `+${tags.length - 6}`) : null),
      e.error ? h("div", { class: "error small registry-card-error", title: e.error }, e.error) : null,
    ),
  );
}

function variantWord(count: number): string {
  if (count % 100 >= 11 && count % 100 <= 14) return ui("core.variantMany");
  if (count % 10 === 1) return ui("core.variantOne");
  if (count % 10 >= 2 && count % 10 <= 4) return ui("core.variantFew");
  return ui("core.variantMany");
}
