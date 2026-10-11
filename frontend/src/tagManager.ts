import { entityTitle, ui } from "./i18n";
import "./tagManager.css";

import { api, KIND_LABEL, type EntitySummary, type TagChange, type TagSummary } from "./api";
import { openModal } from "./branchForm";
import { h, mount, toast } from "./dom";

type TagKind = "components" | "assets";
let managerOpen = false;

/** Bulk tag metadata editor shared by the component and asset catalogs. */
export async function openTagManager(onChanged: (change: TagChange) => Promise<void> | void): Promise<void> {
  if (managerOpen) return;
  managerOpen = true;
  let active = true;
  let loading = true;
  let hasSnapshot = false;
  let busy = false;
  let version = 0;
  let tags: TagSummary[] = [];
  let selected: string | null = null;
  let editedName = "";
  let confirmingDelete = false;
  let kind: TagKind | "all" = "all";
  const entities = new Map<string, EntitySummary>();

  const tagList = h("div", { class: "tag-manager-list", role: "group", "aria-label": ui("tags.title") });
  const searchStatus = h("span", { class: "muted small", role: "status" });
  const search = h("input", { type: "search", placeholder: ui("tags.search"), "aria-label": ui("tags.searchLabel"),
    onInput: () => drawList() });
  const content = h("section", { class: "tag-manager-content", tabindex: -1, "aria-label": ui("tags.related") });
  const errorBox = h("div", { class: "tag-manager-error error small", role: "alert", hidden: true });
  const footerStatus = h("span", { class: "muted small", role: "status", "aria-live": "polite" },
    ui("tags.changeHelp"));
  const body = h("div", { class: "tag-manager" },
    h("aside", { class: "tag-manager-sidebar" },
      h("label", { class: "field" }, h("span", { class: "field-label" }, ui("tags.registry")), search),
      searchStatus, tagList),
    h("div", { class: "tag-manager-main" }, errorBox, content));
  const modal = openModal(ui("tags.manage"), body,
    h("div", { class: "tag-manager-footer" }, footerStatus,
      h("button", { class: "btn", type: "button", onClick: () => modal.close() }, ui("common.close"))),
    { className: "modal-tags", onClose: () => { active = false; managerOpen = false; ++version; } });

  const showError = (error: unknown) => {
    if (!active) return;
    mount(errorBox, h("p", null, error instanceof Error ? error.message : String(error)),
      h("button", { class: "btn btn-sm", type: "button", onClick: () => {
        if (!busy) { content.focus({ preventScroll: true }); void load(selected); }
      } }, ui("common.reload")));
    errorBox.hidden = false;
  };
  const clearError = () => { errorBox.hidden = true; errorBox.textContent = ""; };

  const choose = (name: string) => {
    if (busy) return;
    selected = name;
    editedName = name;
    confirmingDelete = false;
    clearError();
    drawList();
    drawContent();
    tagList.querySelector<HTMLElement>(`[data-tag-name="${CSS.escape(name)}"]`)?.focus({ preventScroll: true });
  };

  const drawList = () => {
    if (!active) return;
    const query = search.value.trim().toLocaleLowerCase("ru");
    const visible = tags.filter((tag) => tag.name.toLocaleLowerCase("ru").includes(query));
    search.disabled = loading || !hasSnapshot;
    searchStatus.textContent = loading ? ui("common.loading") : !hasSnapshot ? ui("tags.unavailable") : ui("dynamic.tagCount", { visible: visible.length, total: tags.length });
    mount(tagList, visible.length ? visible.map((tag) => h("button", {
      class: `tag-manager-tag${tag.name === selected ? " active" : ""}`, type: "button", disabled: busy,
      "data-tag-name": tag.name, "aria-pressed": tag.name === selected,
      onClick: () => choose(tag.name),
    }, h("span", { class: "mono" }, tag.name), h("span", { class: "tag-manager-count muted small" }, `${tag.entity_count}`)))
      : h("p", { class: "muted small" }, loading ? ui("tags.loading") : !hasSnapshot ? ui("tags.reloadHelp") : query ? ui("tags.notFound") : ui("tags.noTags")));
  };

  const entityCard = (entity: EntitySummary) => {
    const thumb = h("div", { class: "card-thumb" });
    const fallback = () => mount(thumb, h("div", { class: "thumb-empty" }, ui("common.noPreview")));
    if (entity.preview?.url) mount(thumb, h("img", { src: entity.preview.url, alt: entityTitle(entity),
      loading: "lazy", decoding: "async", onError: fallback }));
    else fallback();
    return h("a", { class: "card tag-manager-card", href: `#/${entity.kind}/${entity.id}` }, thumb,
      h("div", { class: "card-body" }, h("strong", null, entityTitle(entity)),
        h("span", { class: "muted small mono" }, entity.id),
        h("span", { class: "muted small" }, KIND_LABEL[entity.kind],
          entity.abstract ? ui("tags.base") : entity.type === "structure" ? ui("tags.structure") : ""),
        h("div", { class: "chips" }, [...new Set([...entity.tags, ...entity.variant_tags])]
          .map((tag) => h("span", { class: `chip${tag === selected ? " chip-priority" : ""}` }, tag)))));
  };

  const drawContent = () => {
    if (!active) return;
    const restore = content.contains(document.activeElement);
    const focused = restore ? (document.activeElement as HTMLElement).dataset.tagControl : undefined;
    const restoreFocus = () => {
      if (!restore) return;
      const target = focused ? content.querySelector<HTMLElement>(`[data-tag-control="${CSS.escape(focused)}"]`) : null;
      (target && !target.matches(":disabled") ? target : content.querySelector<HTMLInputElement>("input:not(:disabled)") ?? content)
        .focus({ preventScroll: true });
    };
    const tag = tags.find((entry) => entry.name === selected);
    if (loading) {
      mount(content, h("div", { class: "loading", role: "status" }, ui("tags.loadingCards")));
      restoreFocus();
      return;
    }
    if (!hasSnapshot) {
      mount(content, h("div", { class: "tag-manager-empty muted" }, ui("tags.unavailableRetry")));
      restoreFocus();
      return;
    }
    if (!tag) {
      mount(content, h("div", { class: "tag-manager-empty muted" }, tags.length
        ? ui("tags.selectHelp") : ui("tags.noEntityTags")));
      restoreFocus();
      return;
    }
    const input = h("input", { type: "text", value: editedName, "aria-label": ui("tags.newName"), "data-tag-control": "name", disabled: busy,
      onInput: () => {
        editedName = input.value;
        save.disabled = busy || !editedName.trim() || editedName.trim() === tag.name;
        mergeHint.hidden = !tags.some((entry) => entry.name === editedName.trim() && entry.name !== tag.name);
      },
      onKeydown: (event: KeyboardEvent) => {
        if (event.key === "Enter" && !save.disabled) { event.preventDefault(); void changeTag(false); }
      } });
    const save = h("button", { class: "btn btn-primary", type: "button", "data-tag-control": "save",
      disabled: busy || !editedName.trim() || editedName.trim() === tag.name, onClick: () => void changeTag(false) },
      busy ? ui("common.saving") : ui("tags.saveAll"));
    const mergeHint = h("p", { class: "small muted", hidden: !tags.some((entry) => entry.name === editedName.trim() && entry.name !== tag.name) },
      ui("tags.mergeHelp"));
    const related = tag.entities.map((ref) => entities.get(`${ref.kind}/${ref.id}`)).filter((entity): entity is EntitySummary => Boolean(entity));
    const visible = related.filter((entity) => kind === "all" || entity.kind === kind);
    const kinds: (TagKind | "all")[] = ["all", "components", "assets"];
    mount(content,
      h("div", { class: "tag-manager-heading" }, h("h2", { class: "mono" }, tag.name),
        h("p", { class: "muted small" }, ui("dynamic.tagRelations", { entities: tag.entity_count, variants: tag.variant_count }))),
      confirmingDelete ? h("div", { class: "tag-manager-confirm box box-error" },
        h("strong", null, ui("dynamic.deleteTag", { name: tag.name })),
        h("p", { class: "small" }, ui("dynamic.tagRemovalHelp")),
        h("div", { class: "actions" },
          h("button", { class: "btn btn-danger", type: "button", "data-tag-control": "confirm", disabled: busy, onClick: () => void changeTag(true) }, busy ? ui("tags.deleting") : ui("tags.deleteAll")),
          h("button", { class: "btn", type: "button", "data-tag-control": "cancel", disabled: busy, onClick: () => { confirmingDelete = false; drawContent(); } }, ui("common.cancel"))))
        : h("div", { class: "tag-manager-editor" },
          h("label", { class: "field" }, h("span", { class: "field-label" }, ui("tags.name")), input),
          h("div", { class: "actions" }, save,
            h("button", { class: "btn btn-danger", type: "button", "data-tag-control": "delete", disabled: busy,
              onClick: () => { confirmingDelete = true; clearError(); drawContent(); content.querySelector<HTMLElement>(".tag-manager-confirm button")?.focus(); } }, ui("tags.delete"))),
          mergeHint),
      h("div", { class: "tag-manager-kind btn-group", role: "group", "aria-label": ui("tags.relatedType") },
        kinds.map((value) => h("button", { class: `btn btn-sm btn-toggle${kind === value ? " active" : ""}`, type: "button", "aria-pressed": kind === value, "data-tag-control": `kind:${value}`,
          onClick: () => { kind = value; drawContent(); } },
          `${value === "all" ? ui("common.all") : KIND_LABEL[value]} (${related.filter((entity) => value === "all" || entity.kind === value).length})`))),
      visible.length ? h("div", { class: "card-grid tag-manager-cards" }, visible.map(entityCard))
        : h("p", { class: "muted small" }, related.length ? ui("tags.noRelated") : ui("tags.onlySettings")));
    restoreFocus();
  };

  const load = async (preferred = selected) => {
    const token = ++version;
    loading = true;
    clearError();
    drawList();
    drawContent();
    try {
      const [catalog, components, assets] = await Promise.all([api.tags(), api.list("components"), api.list("assets")]);
      if (!active || token !== version) return;
      tags = catalog.tags;
      hasSnapshot = true;
      entities.clear();
      for (const entity of [...components, ...assets]) entities.set(`${entity.kind}/${entity.id}`, entity);
      selected = tags.some((tag) => tag.name === preferred) ? preferred : tags[0]?.name ?? null;
      editedName = selected ?? "";
      confirmingDelete = false;
      return true;
    } catch (error) {
      if (active && token === version) showError(error);
      return false;
    } finally {
      if (active && token === version) {
        loading = false;
        drawList();
        drawContent();
      }
    }
  };

  const changeTag = async (remove: boolean) => {
    if (!active || busy || selected === null) return;
    const oldName = selected;
    const nextName = editedName.trim();
    if (!remove && (!nextName || nextName === oldName)) return;
    busy = true;
    clearError();
    drawList();
    drawContent();
    let changed: TagChange | null = null;
    try {
      changed = remove ? await api.deleteTag(oldName) : await api.renameTag(oldName, nextName);
      // Discard the old entry immediately: a failed refresh must never expose stale write actions.
      tags = tags.filter((tag) => tag.name !== oldName);
      selected = changed.name;
      editedName = changed.name ?? "";
      confirmingDelete = false;
      const message = remove ? ui("dynamic.tagRemoved", { name: oldName }) : ui("dynamic.tagRenamed", { old: oldName, name: changed.name ?? "" });
      toast(ui("dynamic.tagsUpdated", { message, entities: changed.changed_entities, variants: changed.changed_variants }), "ok");
      await onChanged(changed);
      if (active && await load(changed.name) === false) {
        showError(ui("tags.refreshError"));
      }
    } catch (error) {
      // If the write succeeded, a refresh failure must not invite repeating that write.
      if (changed) {
        if (active) { selected = changed.name; editedName = changed.name ?? ""; await load(changed.name); }
        showError(ui("tags.catalogRefreshError"));
      } else showError(error);
    } finally {
      busy = false;
      if (active) { drawList(); drawContent(); }
    }
  };

  await load();
}
