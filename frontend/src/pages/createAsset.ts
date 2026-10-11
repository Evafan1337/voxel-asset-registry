import { entityTitle, ui } from "../i18n";
// Create a new asset definition and its first variant from built components/assets.

import "./createAsset.css";
import { api, ApiError, type ComposeOption, type NewAssetBody, type Vec3 } from "../api";
import { h, mount, STATUS_LABEL, toast } from "../dom";

interface PartRow {
  name: string;
  ref: string;
  host: string;
  socket: string;
  offset: Vec3;
  autoName: boolean;
}

const ID_RE = /^[a-z][a-z0-9_]*$/;
const humanName = (o: ComposeOption): string => `${o.kind === "assets" ? ui("core.asset") : ui("core.component")} · ${entityTitle(o)} · ${o.variant} · ${STATUS_LABEL[o.status] ?? o.status}`;
const uniqueName = (stem: string, rows: PartRow[]): string => {
  const base = stem.replace(/[^a-z0-9_]/g, "_").replace(/^_+/, "") || "part";
  let name = base;
  let n = 2;
  while (rows.some((row) => row.name === name)) name = `${base}_${n++}`;
  return name;
};

export async function renderCreateAsset(root: HTMLElement): Promise<() => void> {
  const options = (await api.composeOptions()).filter((o) => o.built);
  const byRef = new Map(options.map((o) => [o.ref, o]));
  const rows: PartRow[] = [{ name: "body", ref: "", host: "", socket: "", offset: [0, 0, 0], autoName: false }];
  const fields = {
    id: h("input", { type: "text", placeholder: "my_factory", required: true, pattern: "[a-z][a-z0-9_]*" }),
    title: h("input", { type: "text", placeholder: ui("create.assetName"), required: true }),
    description: h("textarea", { rows: 3, placeholder: ui("create.description") }),
    level: h("select", null, [1, 2, 3].map((n) => h("option", { value: n, selected: n === 1 }, `L${n}`))),
    tags: h("input", { type: "text", placeholder: ui("tags.input") }),
    note: h("textarea", { rows: 2, placeholder: ui("create.firstVariant") }),
    grid: [48, 40, 32].map((n) => h("input", { type: "number", min: 1, max: 256, step: 1, value: n })) as [HTMLInputElement, HTMLInputElement, HTMLInputElement],
  };
  const partsBox = h("div", { class: "new-asset-parts" });
  const errors = h("div", { class: "form-errors", role: "alert" });
  const submit = h("button", { class: "btn btn-primary", type: "button" }, ui("build.create"));

  const candidateSelect = (row: PartRow) => h("select", {
    class: "new-asset-choice",
    "aria-label": ui("dynamic.slotVariant", { name: row.name }),
    onChange: (ev: Event) => {
      row.ref = (ev.target as HTMLSelectElement).value;
      const candidate = byRef.get(row.ref);
      if (candidate && row.autoName) row.name = uniqueName(candidate.id, rows.filter((other) => other !== row));
      row.host = "";
      row.socket = "";
      drawRows();
    },
  },
    h("option", { value: "", selected: !row.ref }, ui("create.chooseVariant")),
    (["components", "assets"] as const).map((kind) => h("optgroup", { label: kind === "components" ? ui("nav.components") : ui("nav.assets") },
      options.filter((o) => o.kind === kind).map((o) => h("option", { value: o.ref, selected: row.ref === o.ref }, humanName(o))))),
  );

  const hostChoices = (index: number): { host: string; socket: string; label: string; type: string }[] => {
    const current = byRef.get(rows[index].ref);
    const occupied = new Set(rows.filter((_, otherIndex) => otherIndex !== index && otherIndex > 0 && rows[otherIndex].host)
      .map((row) => `${row.host}.${row.socket}`));
    return rows.slice(0, index).flatMap((hostRow) => {
      const host = byRef.get(hostRow.ref);
      return (host?.sockets ?? []).filter((socket) =>
        (!current?.mounts.length || current.mounts.includes(socket.type)) &&
        !occupied.has(`${hostRow.name}.${socket.name}`),
      ).map((socket) => ({ host: hostRow.name, socket: socket.name, label: `${hostRow.name}.${socket.name}`, type: socket.type }));
    });
  };

  const drawRows = () => {
    mount(partsBox, rows.map((row, index) => {
      const candidate = byRef.get(row.ref);
      const attachment = index ? hostChoices(index) : [];
      const socketValue = row.host && row.socket ? `${row.host}.${row.socket}` : "";
      return h("div", { class: "new-asset-part" },
        h("div", { class: "new-asset-part-head" },
          h("strong", null, index === 0 ? ui("create.base") : ui("dynamic.partNumber", { number: index + 1 })),
          index > 0 ? h("button", { class: "btn btn-sm", type: "button", title: ui("create.removeSlot"), onClick: () => {
            rows.splice(index, 1);
            for (const child of rows) if (child.host === row.name) { child.host = ""; child.socket = ""; }
            drawRows();
          } }, ui("common.remove")) : null,
        ),
        h("div", { class: "new-asset-part-main" },
          h("div", { class: "new-asset-part-preview" }, candidate?.preview
            ? h("img", { src: candidate.preview, alt: candidate.ref })
            : h("span", { class: "muted small" }, ui("common.noPreview"))),
          h("div", { class: "new-asset-part-fields" },
            h("label", null, ui("create.readyModel"), candidateSelect(row)),
            candidate ? h("div", { class: "muted small" },
              candidate.ref, ui("dynamic.attachment", { grid: candidate.grid_size.join("×"), mounts: candidate.mounts.join(", ") || ui("common.any") })) : null,
            index > 0 ? h("div", { class: "new-asset-part-controls" },
              h("label", null, ui("create.slotName"), h("input", { type: "text", value: row.name, onChange: (ev: Event) => {
                const previous = row.name;
                row.name = (ev.target as HTMLInputElement).value.trim();
                row.autoName = false;
                for (const child of rows) if (child.host === previous) child.host = row.name;
                drawRows();
              } })),
              h("label", null, ui("create.attachment"), h("select", {
                value: socketValue,
                onChange: (ev: Event) => {
                  const selected = attachment.find((x) => x.label === (ev.target as HTMLSelectElement).value);
                  row.host = selected?.host ?? "";
                  row.socket = selected?.socket ?? "";
                },
              },
                h("option", { value: "", selected: !socketValue }, ui("create.chooseSocket")),
                attachment.map((x) => h("option", { value: x.label, selected: x.label === socketValue }, `${x.label} · ${x.type}`)),
              )),
            ) : h("div", { class: "muted small" }, ui("create.origin")),
            index > 0 ? h("div", { class: "new-asset-offset" },
              h("span", { class: "muted small" }, ui("create.offset")),
              (["X", "Y", "Z"] as const).map((axis, n) => h("label", null, axis,
                h("input", { type: "number", min: -10, max: 10, step: 0.25, value: row.offset[n], onChange: (ev: Event) => {
                  const value = Number((ev.target as HTMLInputElement).value);
                  if (Number.isFinite(value)) row.offset[n] = value;
                } }))),
            ) : null,
            index > 0 && candidate && !attachment.length
              ? h("p", { class: "error small" }, ui("create.noSocket")) : null,
          ),
        ),
      );
    }));
  };

  const validation = (): string[] => {
    const problems: string[] = [];
    if (!ID_RE.test(fields.id.value.trim())) problems.push(ui("create.invalidId"));
    if (!fields.title.value.trim()) problems.push(ui("create.needName"));
    if (!rows[0].ref) problems.push(ui("create.needBody"));
    const names = new Set<string>();
    rows.forEach((row, index) => {
      if (!ID_RE.test(row.name)) problems.push(ui("dynamic.slotInvalidName", { name: index + 1 }));
      if (names.has(row.name)) problems.push(ui("dynamic.slotDuplicate", { name: row.name }));
      names.add(row.name);
      if (!row.ref || !byRef.has(row.ref)) problems.push(ui("dynamic.slotChoose", { name: row.name }));
      if (index > 0 && (!row.host || !row.socket)) problems.push(ui("dynamic.slotChooseSocket", { name: row.name }));
      if (index > 0 && !hostChoices(index).some((x) => x.host === row.host && x.socket === row.socket))
        problems.push(ui("dynamic.slotIncompatible", { name: row.name }));
      if (row.offset.some((x) => !Number.isFinite(x) || Math.abs(x) > 10)) problems.push(ui("dynamic.slotOffset", { name: row.name }));
    });
    if (fields.grid.some((input) => !Number.isInteger(Number(input.value)) || Number(input.value) < 1 || Number(input.value) > 256))
      problems.push(ui("create.gridError"));
    return problems;
  };

  submit.addEventListener("click", async () => {
    const problems = validation();
    mount(errors, problems.map((message) => h("div", null, `✗ ${message}`)));
    if (problems.length) return;
    submit.disabled = true;
    const body: NewAssetBody = {
      id: fields.id.value.trim(),
      title: fields.title.value.trim(),
      description: fields.description.value.trim(),
      grid_size: fields.grid.map((input) => Number(input.value)) as Vec3,
      voxel_size: 0.25,
      pivot: "bottom_center",
      sockets: [],
      slots: Object.fromEntries(rows.map((row, index) => [row.name, {
        socket: index ? `${row.host}.${row.socket}` : null,
        accepts: [row.ref.startsWith("assets/") ? `assets/${byRef.get(row.ref)!.id}` : byRef.get(row.ref)!.id],
        max_grid: byRef.get(row.ref)!.grid_size,
        required: true,
        description: "",
      }])),
      variant: {
        slots: Object.fromEntries(rows.map((row) => [row.name, row.ref])),
        slot_offsets: Object.fromEntries(rows.filter((row, index) => index > 0 && row.offset.some((x) => x !== 0)).map((row) => [row.name, row.offset])),
        level: Number(fields.level.value),
        note: fields.note.value.trim(),
        tags: fields.tags.value.split(",").map((tag) => tag.trim()).filter(Boolean),
      },
      build: true,
    };
    try {
      const created = await api.createAsset(body);
      toast(ui("dynamic.created", { ref: `${body.id}@${created.id}` }), "ok");
      location.hash = `#/assets/${body.id}?v=${created.id}`;
    } catch (error) {
      const messages = error instanceof ApiError && error.errors.length ? error.errors : [(error as Error).message];
      mount(errors, messages.map((message) => h("div", null, `✗ ${message}`)));
      submit.disabled = false;
    }
  });

  drawRows();
  mount(root, h("section", { class: "page page-new-asset" },
    h("div", { class: "entity-head" },
      h("div", null,
        h("div", { class: "crumbs" }, h("a", { href: "#/assets" }, ui("nav.assets")), ui("core.newBreadcrumb")),
        h("h1", null, ui("create.title")),
        h("p", { class: "muted" }, ui("create.help")),
      ),
    ),
    h("div", { class: "new-asset-layout" },
      h("div", { class: "new-asset-assembly" },
        h("h2", null, ui("create.composition")),
        partsBox,
        h("button", { class: "btn", type: "button", onClick: () => {
          rows.push({ name: uniqueName("part", rows), ref: "", host: "", socket: "", offset: [0, 0, 0], autoName: true });
          drawRows();
        } }, ui("create.addPart")),
      ),
      h("div", { class: "new-asset-meta" },
        h("h2", null, ui("create.bounds")),
        h("label", null, "ID", fields.id),
        h("label", null, ui("common.name"), fields.title),
        h("label", null, ui("common.description"), fields.description),
        h("label", null, ui("common.level"), fields.level),
        h("label", null, ui("create.grid"), h("span", { class: "new-asset-grid" },
          (["X", "Y", "Z"] as const).map((axis, i) => h("span", null, axis, fields.grid[i])))),
        h("p", { class: "muted small" }, ui("create.voxelHelp")),
        h("label", null, ui("create.tags"), fields.tags),
        h("label", null, ui("create.variantNote"), fields.note),
        errors,
        h("div", { class: "btn-group" }, h("a", { class: "btn", href: "#/assets" }, ui("common.cancel")), submit),
      ),
    ),
  ));
  return () => {};
}
