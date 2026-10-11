import { entityTitle, parameterLabel, ui } from "../i18n";
// Asset assembly: pick a compatible component or asset variant for every slot.

import { api, ApiError, type SlotOption, type VariantDetail } from "../api";
import { h, mount, stars, toast } from "../dom";
import { makeParamInput } from "../branchForm";

export async function renderCompose(root: HTMLElement, id: string, query: URLSearchParams): Promise<() => void> {
  const [entity, options, tree] = await Promise.all([api.entity("assets", id), api.slotOptions(id), api.tree("assets", id)]);
  let parentId: string | null = query.get("parent") ?? null;
  let parent: VariantDetail | null = parentId ? await api.variant("assets", id, parentId) : null;
  const choice = new Map<string, string | null>();

  const slotsBox = h("div", { class: "compose-slots" });
  const paramsBox = h("div", { class: "section compose-params" });
  const paramFields = new Map<string, () => unknown>();
  const errors = h("div", { class: "form-errors" });
  const note = h("textarea", { rows: 2, placeholder: ui("compose.note") });
  const tags = h("input", { type: "text", placeholder: ui("tags.input") });
  const level = h("select", null, [0, 1, 2, 3].map((l) => h("option", { value: l }, `L${l}`)));

  const resetChoices = () => {
    choice.clear();
    for (const [name] of Object.entries(entity.slots)) {
      const fromParent = parent?.slots?.find((s) => s.name === name)?.ref ?? null;
      const opts = options[name] ?? [];
      const fallback = entity.slots[name].required ? pickBest(opts)?.ref ?? null : null;
      choice.set(name, parent ? fromParent : fallback);
    }
    if (parent) level.value = String(parent.variant.level);
  };

  const drawSlots = () => {
    mount(slotsBox, Object.entries(entity.slots).map(([name, spec]) => {
      const opts = options[name] ?? [];
      const current = choice.get(name) ?? null;
      const parentRef = parent?.slots?.find((s) => s.name === name)?.ref ?? null;
      const changed = parent !== null && current !== parentRef;
      const selectedOpt = opts.find((o) => o.ref === current);
      const select = h("select", {
        onChange: (ev: Event) => {
          const v = (ev.target as HTMLSelectElement).value;
          choice.set(name, v === "" ? null : v);
          drawSlots();
        },
      },
        !spec.required || !current ? h("option", { value: "", selected: !current }, spec.required ? ui("compose.select") : ui("compose.empty")) : null,
        current && !selectedOpt ? h("option", { value: current, selected: true }, ui("dynamic.incompatible", { ref: current })) : null,
        groupByComponent(opts).map(([comp, list]) => h("optgroup", { label: comp },
          list.map((o) => h("option", { value: o.ref, selected: o.ref === current }, optionLabel(o))))),
      );
      return h("div", { class: `compose-slot${changed ? " changed" : ""}` },
        h("div", { class: "compose-thumb" },
          selectedOpt?.preview ? h("img", { src: selectedOpt.preview, alt: selectedOpt.ref })
            : h("div", { class: "thumb-empty" }, ui("common.noPreview"))),
        h("div", { class: "compose-info" },
          h("div", { class: "row-between" },
            h("strong", { class: "mono" }, name),
            h("span", { class: "muted small" }, spec.socket
              ? (spec.socket.includes(".") ? ui("dynamic.socket", { name: spec.socket }) : ui("dynamic.bodySocket", { name: spec.socket }))
              : ui("compose.body"))),
          h("div", { class: "muted small" },
            spec.description || "", ui("dynamic.accepts", { accepts: spec.accepts.join(", ") || ui("common.all"), grid: spec.max_grid.join("×") }),
            spec.required ? ui("core.required") : ui("core.optional")),
          select,
          selectedOpt ? h("div", { class: "small" }, stars(selectedOpt.rating), " ", selectedOpt.note) : null,
          !opts.length ? h("div", { class: "error small" }, ui("compose.noCompatible")) : null,
          changed ? h("div", { class: "small accent" }, ui("dynamic.previous", { value: parentRef ?? ui("common.empty") })) : null,
        ),
      );
    }));
  };

  const parameterBaseline = (name: string) => parent?.params?.[name] ?? entity.params[name].default;
  const drawParameters = () => {
    paramFields.clear();
    const names = Object.keys(entity.params);
    mount(paramsBox, names.length ? [h("h3", null, ui("compose.params")), ...names.map((name) => {
      const spec = entity.params[name];
      const baseline = parameterBaseline(name);
      const input = makeParamInput(spec, baseline, () => {
        row.classList.toggle("changed", JSON.stringify(input.read()) !== JSON.stringify(baseline));
      });
      const controls = input.el.matches("input, select") ? [input.el] : [...input.el.querySelectorAll("input, select")];
      controls.forEach((el) => el.setAttribute("aria-label", parameterLabel(name)));
      const row = h("div", { class: "form-row" }, h("label", null,
        h("span", { class: "param-name" }, parameterLabel(name)),
        spec.description ? h("span", { class: "muted small" }, spec.description) : null), input.el);
      paramFields.set(name, input.read);
      return row;
    })] : []);
  };

  const parentSelect = h("select", {
    onChange: async (ev: Event) => {
      const v = (ev.target as HTMLSelectElement).value;
      parentId = v || null;
      parent = parentId ? await api.variant("assets", id, parentId) : null;
      history.replaceState(null, "", `#/assets/${id}/compose${parentId ? `?parent=${parentId}` : ""}`);
      resetChoices();
      drawSlots();
      drawParameters();
    },
  },
    h("option", { value: "", selected: !parentId }, ui("compose.newRoot")),
    tree.nodes.map((n) => h("option", { value: n.id, selected: n.id === parentId }, `${n.id} — ${n.note || n.status}`)),
  );

  const submit = h("button", { class: "btn btn-primary" }, ui("build.build"));
  submit.addEventListener("click", async () => {
    const invalid = paramsBox.querySelector<HTMLInputElement>("input:invalid");
    if (invalid) { invalid.reportValidity(); invalid.focus(); return; }
    const paramsDelta: Record<string, unknown> = {};
    for (const [name, read] of paramFields) {
      const value = read();
      if (typeof value === "number" && !Number.isFinite(value)) {
        errors.textContent = ui("error.number", { name });
        return;
      }
      if (JSON.stringify(value) !== JSON.stringify(parameterBaseline(name))) paramsDelta[name] = value;
    }
    submit.disabled = true;
    errors.textContent = "";
    try {
      const created = await api.createVariant("assets", id, {
        parent: parentId,
        slots: Object.fromEntries(choice),
        params_delta: paramsDelta,
        note: note.value.trim(),
        tags: tags.value.split(",").map((t) => t.trim()).filter(Boolean),
        level: Number(level.value),
      });
      toast(ui("dynamic.created", { ref: `${id}@${created.id}` }), "ok");
      location.hash = `#/assets/${id}?v=${created.id}`;
    } catch (err) {
      const list = err instanceof ApiError && err.errors.length ? err.errors : [(err as Error).message];
      errors.replaceChildren(...list.map((e) => h("div", null, `✗ ${e}`)));
      submit.disabled = false;
    }
  });

  resetChoices();
  drawSlots();
  drawParameters();
  mount(root, h("section", { class: "page page-compose" },
    h("div", { class: "entity-head" },
      h("div", null,
        h("div", { class: "crumbs" }, h("a", { href: "#/assets" }, ui("nav.assets")), " / ", h("a", { href: `#/assets/${id}` }, id), ui("core.composeBreadcrumb")),
        h("h1", null, ui("dynamic.composeTitle", { title: entityTitle(entity) })),
        h("div", { class: "muted small" }, ui("compose.help"))),
    ),
    h("div", { class: "compose-layout" },
      h("div", null,
        h("div", { class: "form-row" }, h("label", null, h("span", { class: "param-name" }, ui("compose.parent"))), parentSelect),
        paramsBox, slotsBox),
      h("div", { class: "compose-side" },
        h("div", { class: "form-row" }, h("label", null, h("span", { class: "param-name" }, "level")), level),
        h("div", { class: "form-row" }, h("label", null, h("span", { class: "param-name" }, "note")), note),
        h("div", { class: "form-row" }, h("label", null, h("span", { class: "param-name" }, "tags")), tags),
        errors,
        h("div", { class: "btn-group" }, h("a", { class: "btn", href: `#/assets/${id}` }, ui("common.cancel")), submit),
        h("p", { class: "muted small" }, ui("compose.deltaHelp")),
      ),
    ),
  ));
  return () => {};
}

function pickBest(opts: SlotOption[]): SlotOption | undefined {
  return opts.find((o) => o.status === "approved") ?? opts[0];
}

function groupByComponent(opts: SlotOption[]): [string, SlotOption[]][] {
  const groups = new Map<string, SlotOption[]>();
  for (const o of opts) {
    if (!groups.has(o.component)) groups.set(o.component, []);
    groups.get(o.component)!.push(o);
  }
  return [...groups.entries()];
}

function optionLabel(o: SlotOption): string {
  const parts = [o.ref, o.status === "approved" ? `✓ ${ui("status.approved")}` : ui("status.built"), `L${o.level}`];
  if (o.rating) parts.push("★".repeat(o.rating));
  if (o.note) parts.push(o.note);
  return parts.join(" · ");
}
