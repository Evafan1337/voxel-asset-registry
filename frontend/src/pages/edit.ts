import { entityTitle, ui } from "../i18n";
// Placement editor for built asset variants. Edits are saved as a new child variant.

import { api, ApiError, type SlotResolution, type Vec3 } from "../api";
import { h, mount, toast } from "../dom";
import { ViewerPanel } from "../viewerPanel";

const STEP = 0.25;
const MAX_OFFSET = 10;
const ZERO: Vec3 = [0, 0, 0];
const AXES: { index: 0 | 1 | 2; name: string; direction: string; minus: string; plus: string }[] = [
  { index: 0, name: "X", direction: ui("edit.leftRight"), minus: "←", plus: "→" },
  { index: 1, name: "Y", direction: ui("edit.downUp"), minus: "↓", plus: "↑" },
  { index: 2, name: "Z", direction: ui("edit.backForward"), minus: ui("edit.backDirection"), plus: ui("edit.forward") },
];

export async function renderEdit(root: HTMLElement, id: string, query: URLSearchParams): Promise<() => void> {
  const [entity, tree] = await Promise.all([api.entity("assets", id), api.tree("assets", id)]);
  const sourceId = query.get("parent") ??
    [...tree.nodes].reverse().find((node) => node.build_state === "ok")?.id ?? tree.nodes.at(-1)?.id;
  if (!sourceId) throw new Error(ui("dynamic.noEditVariant", { id }));
  const parent = await api.variant("assets", id, sourceId);
  const slots = (parent.slots ?? []).filter((slot) => slot.ref);
  const byName = new Map(slots.map((slot) => [slot.name, slot]));
  const baseline = new Map(slots.map((slot) => [slot.name, copy(slot.offset ?? ZERO)]));
  const working = new Map([...baseline].map(([name, offset]) => [name, copy(offset)]));
  let selected = slots.find((slot) => slot.socket)?.name ?? slots[0]?.name ?? null;
  let saving = false;
  let snap: number | null = STEP;

  const panel = new ViewerPanel(`${id}@${sourceId}${ui("dynamic.placementSuffix")}`, { editor: true });
  const slotList = h("div", { class: "edit-slot-list" });
  const inspector = h("div", { class: "edit-inspector" });
  const status = h("span", { class: "muted small" });
  const errors = h("div", { class: "form-errors" });
  const note = h("textarea", { rows: 2, placeholder: ui("edit.notePlaceholder") });
  const save = h("button", { class: "btn btn-primary", disabled: true }, ui("edit.save"));
  const revertAll = h("button", { class: "btn" }, ui("edit.revert"));
  const snapSelect = h("select", { class: "select-sm", "aria-label": ui("edit.snapHint") },
    h("option", { value: "0.25", selected: true }, ui("edit.quarterVoxel")),
    h("option", { value: "0.1" }, ui("edit.tenth")),
    h("option", { value: "0.5" }, ui("edit.half")),
    h("option", { value: "off" }, ui("edit.noSnap")));
  const sourceSelect = h("select", {
    class: "select-sm",
    onChange: () => { location.hash = `#/assets/${id}/edit?parent=${sourceSelect.value}`; },
  }, tree.nodes.map((node) => h("option", { value: node.id, selected: node.id === sourceId },
    `${node.id} · ${node.build_state === "ok" ? ui("status.built") : node.build_state}`)));

  mount(root, h("section", { class: "page page-edit" },
    h("div", { class: "entity-head" },
      h("div", null,
        h("div", { class: "crumbs" }, h("a", { href: "#/assets" }, ui("nav.assets")), " / ",
          h("a", { href: `#/assets/${id}?v=${sourceId}` }, id), ui("core.editBreadcrumb")),
        h("h1", null, ui("dynamic.editTitle", { title: entityTitle(entity) })),
        h("div", { class: "muted small" }, ui("edit.help"))),
      h("a", { class: "btn", href: `#/assets/${id}?v=${sourceId}` }, ui("edit.back"))),
    h("div", { class: "edit-layout" },
      h("aside", { class: "pane edit-list-pane" },
        h("div", { class: "pane-head" }, h("strong", null, ui("entity.slots"))),
        h("label", { class: "edit-source muted small" }, ui("edit.source"), sourceSelect),
        slotList),
      h("section", { class: "pane center-pane" }, panel.el),
      h("aside", { class: "pane edit-side-pane" },
        h("div", { class: "pane-head" }, h("strong", null, ui("edit.position"))),
        h("label", { class: "edit-snap" },
          h("span", { class: "field-label" }, ui("edit.snap")), snapSelect),
        h("div", { class: "muted small" }, ui("edit.dragHelp")),
        inspector,
        h("div", { class: "section edit-save" },
          h("label", { class: "field" }, h("span", { class: "field-label" }, ui("edit.note")), note),
          errors,
          status,
          h("div", { class: "actions" }, revertAll, save)))),
  ));

  const available = new Set<string>();
  const isDirty = (name: string): boolean => !same(working.get(name) ?? ZERO, baseline.get(name) ?? ZERO);
  const changes = (): Record<string, Vec3> => Object.fromEntries(
    slots.filter((slot) => isDirty(slot.name)).map((slot) => [slot.name, copy(working.get(slot.name) ?? ZERO)]),
  );

  const drawList = () => {
    mount(slotList, slots.length ? slots.map((slot) => h("button", {
      class: `edit-slot${slot.name === selected ? " selected" : ""}${isDirty(slot.name) ? " changed" : ""}`,
      onClick: () => choose(slot.name),
      title: available.has(slot.name) ? ui("edit.choosePart") : ui("edit.noNode"),
    },
    h("span", { class: "edit-slot-name mono" }, slot.name),
    h("span", { class: "muted small" }, slot.ref ?? ""),
    h("span", { class: "edit-slot-meta muted small" },
      slot.socket ? `↳ ${slot.socket}` : ui("entity.body"), isDirty(slot.name) ? ui("core.modifiedDot") : "")))
      : h("p", { class: "muted" }, ui("edit.noneOccupied")));
  };

  const applyPreview = () => {
    const deltas: Record<string, Vec3> = {};
    for (const slot of slots) {
      const current = working.get(slot.name) ?? ZERO;
      const original = baseline.get(slot.name) ?? ZERO;
      deltas[slot.name] = [current[0] - original[0], current[1] - original[1], current[2] - original[2]];
    }
    panel.viewer.applySlotDeltas(deltas);
    const count = Object.keys(changes()).length;
    status.textContent = count ? ui("dynamic.changedSlots", { count }) : ui("common.noChanges");
    save.disabled = saving || count === 0;
    revertAll.disabled = count === 0;
    drawList();
  };

  const setOffset = (name: string, offset: Vec3) => {
    if (!offset.every(Number.isFinite) || offset.some((value) => Math.abs(value) > MAX_OFFSET)) {
      errors.textContent = ui("dynamic.offsetRange", { max: MAX_OFFSET });
      drawInspector();
      return;
    }
    errors.textContent = "";
    working.set(name, offset.map((value) => Math.round(value * 10000) / 10000) as Vec3);
    applyPreview();
    drawInspector();
  };

  const drawInspector = () => {
    const slot: SlotResolution | undefined = selected ? byName.get(selected) : undefined;
    if (!slot) {
      mount(inspector, h("p", { class: "muted" }, ui("edit.selectSlot")));
      return;
    }
    const offset = working.get(slot.name) ?? ZERO;
    mount(inspector,
      h("h2", { class: "mono" }, slot.name),
      h("div", { class: "muted small" }, `${slot.ref} · ${slot.socket ? ui("dynamic.plainSocket", { name: slot.socket }) : ui("edit.center")}`),
      slot.host ? h("div", { class: "muted small" }, ui("dynamic.host", { host: slot.host })) : null,
      h("p", { class: "muted small" }, ui("edit.offsetHelp")),
      AXES.map((axis) => {
        const input = h("input", {
          type: "number", step: snap ?? "any", min: -MAX_OFFSET, max: MAX_OFFSET, value: String(offset[axis.index]),
          "aria-label": ui("dynamic.meters", { axis: axis.name }),
        });
        input.addEventListener("change", () => {
          const value = Number(input.value);
          if (input.value.trim() === "" || !Number.isFinite(value) || Math.abs(value) > MAX_OFFSET) {
            input.value = String((working.get(slot.name) ?? ZERO)[axis.index]);
            errors.textContent = ui("dynamic.offsetRange", { max: MAX_OFFSET });
            return;
          }
          const next = copy(working.get(slot.name) ?? ZERO);
          next[axis.index] = value;
          setOffset(slot.name, next);
        });
        const nudge = (direction: -1 | 1) => {
          const next = copy(working.get(slot.name) ?? ZERO);
          next[axis.index] += direction * (snap ?? STEP);
          setOffset(slot.name, next);
        };
        return h("div", { class: "edit-axis" },
          h("div", { class: "edit-axis-label" }, h("strong", null, axis.name), h("span", { class: "muted small" }, axis.direction)),
          h("div", { class: "edit-axis-controls" },
            h("button", { class: "btn btn-sm", onClick: () => nudge(-1) }, `${axis.minus} −${fmt(snap ?? STEP)}`),
            input,
            h("button", { class: "btn btn-sm", onClick: () => nudge(1) }, `+${fmt(snap ?? STEP)} ${axis.plus}`)));
      }),
      h("div", { class: "actions edit-reset-actions" },
        h("button", { class: "btn btn-sm", disabled: !isDirty(slot.name), onClick: () => setOffset(slot.name, copy(baseline.get(slot.name) ?? ZERO)) }, ui("edit.restore")),
        h("button", { class: "btn btn-sm", disabled: same(offset, ZERO), onClick: () => setOffset(slot.name, copy(ZERO)) },
          slot.socket ? ui("edit.centerSocket") : ui("edit.centerBody"))),
      isDirty(slot.name) ? h("div", { class: "muted small" },
        ui("dynamic.previous", { value: `${(baseline.get(slot.name) ?? ZERO).map(fmt).join(" / ")} m` })) : null,
    );
  };

  const choose = (name: string) => {
    if (!byName.has(name)) return;
    selected = name;
    panel.viewer.selectSlot(name);
    drawList();
    drawInspector();
  };

  panel.viewer.onSlotPick = choose;
  panel.viewer.onSlotMove = (name, delta) => {
    const original = baseline.get(name);
    if (!original) return;
    const next: Vec3 = [original[0] + delta[0], original[1] + delta[1], original[2] + delta[2]];
    if (next.some((value) => !Number.isFinite(value) || Math.abs(value) > MAX_OFFSET)) {
      errors.textContent = ui("dynamic.offsetRange", { max: MAX_OFFSET });
      applyPreview(); // Return the handle to the last valid position.
      return;
    }
    setOffset(name, next);
  };
  snapSelect.addEventListener("change", () => {
    snap = snapSelect.value === "off" ? null : Number(snapSelect.value);
    panel.viewer.setTranslationSnap(snap);
    drawInspector();
  });
  panel.viewer.setTranslationSnap(snap);
  revertAll.addEventListener("click", () => {
    for (const [name, offset] of baseline) working.set(name, copy(offset));
    applyPreview();
    drawInspector();
  });
  save.addEventListener("click", async () => {
    const slotOffsets = changes();
    if (!Object.keys(slotOffsets).length || saving) return;
    saving = true;
    save.disabled = true;
    errors.textContent = "";
    try {
      const created = await api.createVariant("assets", id, {
        parent: sourceId,
        slot_offsets: slotOffsets,
        level: parent.variant.level,
        author: "human",
        tags: parent.variant.tags,
        build: true,
        note: note.value.trim() || `Ручная правка размещения: ${Object.keys(slotOffsets).join(", ")}`,
      });
      toast(ui("dynamic.created", { ref: `${id}@${created.id}` }), "ok");
      location.hash = `#/assets/${id}?v=${created.id}`;
    } catch (err) {
      const list = err instanceof ApiError && err.errors.length ? err.errors : [(err as Error).message];
      errors.replaceChildren(...list.map((message) => h("div", null, `✗ ${message}`)));
      saving = false;
      save.disabled = false;
    }
  });

  drawList();
  drawInspector();
  applyPreview();
  const meta = { gridSize: entity.interface?.grid_size ?? null, voxelSize: entity.interface?.voxel_size ?? 0.25 };
  const loaded = await panel.show(parent.urls?.model ?? null, meta);
  if (loaded) {
    for (const name of panel.viewer.configureSlotEditing(slots.map((slot) => ({ name: slot.name, host: slot.host })))) available.add(name);
    panel.viewer.applySlotDeltas({});
    panel.viewer.selectSlot(selected);
    drawList();
    if (available.size !== slots.length) panel.setStatus(ui("edit.missingNodes"));
  } else if (!parent.urls?.model) {
    panel.setStatus(ui("edit.originalUnbuilt"));
  }
  const onTheme = () => panel.applyTheme();
  window.addEventListener("themechange", onTheme);
  return () => {
    window.removeEventListener("themechange", onTheme);
    panel.dispose();
  };
}

function copy(value: Vec3): Vec3 { return [value[0], value[1], value[2]]; }
function same(a: Vec3, b: Vec3): boolean { return a.every((value, index) => Math.abs(value - b[index]) < 1e-8); }
function fmt(value: number): string { return Number(value.toFixed(3)).toString(); }
