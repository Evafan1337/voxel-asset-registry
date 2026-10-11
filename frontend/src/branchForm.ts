import { parameterLabel, ui } from "./i18n";
// "Ветка отсюда": form over the parameter schema, prefilled with the parent's resolved values.
// Only changed fields go into the new variant's delta.

import { api, ApiError, type EntityDoc, type ParamSpec, type VariantDetail } from "./api";
import { fmtValue, h } from "./dom";

let modalId = 0;

export function openModal(title: string, body: HTMLElement, footer: HTMLElement,
  options: { className?: string; onClose?: () => void } = {}): { close: () => void } {
  const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const background = [...document.body.children].filter((el): el is HTMLElement => el instanceof HTMLElement)
    .map((el) => ({ el, inert: el.inert }));
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("hashchange", close);
    for (const { el, inert } of background) el.inert = inert;
    if (previousFocus?.isConnected) previousFocus.focus();
    options.onClose?.();
  };
  const onKey = (ev: KeyboardEvent) => {
    if (ev.key === "Escape") { ev.preventDefault(); close(); }
    if (ev.key !== "Tab") return;
    const controls = [...dialog.querySelectorAll<HTMLElement>("button, input, select, textarea, a[href], [tabindex]")]
      .filter((el) => !el.matches(":disabled") && el.tabIndex >= 0 && el.getClientRects().length > 0);
    const first = controls[0];
    const last = controls.at(-1);
    if (!first || !last) { ev.preventDefault(); dialog.focus(); return; }
    if (ev.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
      ev.preventDefault(); last.focus();
    } else if (!ev.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {
      ev.preventDefault(); first.focus();
    }
  };
  const titleId = `modal-title-${++modalId}`;
  const dialog = h("div", { class: `modal${options.className ? ` ${options.className}` : ""}`, role: "dialog", "aria-modal": "true", "aria-labelledby": titleId, tabindex: -1 },
    h("div", { class: "modal-head" }, h("h3", { id: titleId }, title),
      h("button", { class: "btn btn-ghost", "aria-label": ui("common.closeDialog"), onClick: close }, "✕")),
    h("div", { class: "modal-body" }, body), h("div", { class: "modal-foot" }, footer));
  const backdrop = h("div", { class: "modal-backdrop", onClick: (ev: MouseEvent) => { if (ev.target === backdrop) close(); } },
    dialog,
  );
  document.addEventListener("keydown", onKey);
  window.addEventListener("hashchange", close);
  document.body.appendChild(backdrop);
  for (const { el } of background) el.inert = true;
  (body.querySelector<HTMLElement>("input, select, textarea, button") ?? dialog).focus();
  return { close };
}

interface Field {
  name: string;
  spec: ParamSpec;
  read: () => unknown;
  row: HTMLElement;
}

export function makeParamInput(spec: ParamSpec, value: unknown, onInput: () => void): { el: HTMLElement; read: () => unknown } {
  if (spec.type === "color") {
    const el = h("input", { type: "text", value: String(value), onInput });
    return { el, read: () => el.value.trim() };
  }
  if (spec.type === "bool") {
    const el = h("input", { type: "checkbox", checked: Boolean(value), onChange: onInput });
    return { el, read: () => el.checked };
  }
  if (spec.type === "enum") {
    const el = h("select", { onChange: onInput }, (spec.values ?? []).map((v) => h("option", { value: v, selected: v === value }, v)));
    return { el, read: () => el.value };
  }
  const isInt = spec.type === "int";
  const suggestedStep = spec.min != null && spec.max != null ? Math.max((spec.max - spec.min) / 100, 0.0001) : 0.01;
  const step = isInt ? 1 : 10 ** Math.floor(Math.log10(suggestedStep));
  const number = h("input", {
    type: "number", value: String(value), step: isInt ? "1" : "any",
    min: spec.min ?? undefined, max: spec.max ?? undefined, onInput,
  });
  const children: HTMLElement[] = [number];
  if (spec.min != null && spec.max != null) {
    const range = h("input", {
      type: "range", min: spec.min, max: spec.max, step: String(step), value: String(value),
      onInput: () => { number.value = range.value; onInput(); },
    });
    number.addEventListener("input", () => { range.value = number.value; });
    children.unshift(range);
  }
  return {
    el: h("div", { class: "num-input" }, children),
    read: () => number.valueAsNumber,
  };
}

export function openBranchForm(entity: EntityDoc, parent: VariantDetail, onCreated: (vid: string) => void): void {
  const params = parent.params ?? {};
  const fields: Field[] = [];
  const changedCount = h("span", { class: "muted" });

  const refresh = () => {
    let n = 0;
    for (const f of fields) {
      const changed = !sameValue(f.read(), params[f.name]);
      f.row.classList.toggle("changed", changed);
      if (changed) n++;
    }
    changedCount.textContent = n ? ui("branch.changed", { count: n }) : ui("common.nothingChanged");
  };

  const rows = Object.entries(entity.params).map(([name, spec]) => {
    const input = makeParamInput(spec, params[name], () => refresh());
    const controls = input.el.matches("input, select") ? [input.el] : [...input.el.querySelectorAll("input, select")];
    controls.forEach((el) => el.setAttribute("aria-label", parameterLabel(name)));
    const row = h("div", { class: "form-row" },
      h("label", null,
        h("span", { class: "param-name" }, parameterLabel(name)),
        spec.description ? h("span", { class: "muted small" }, spec.description) : null,
        h("span", { class: "muted small" }, rangeHint(spec)),
      ),
      input.el,
      h("span", { class: "muted small parent-value", title: ui("branch.parentValue") }, fmtValue(params[name])),
    );
    fields.push({ name, spec, read: input.read, row });
    return row;
  });

  const note = h("textarea", { rows: 2, placeholder: ui("branch.note") });
  const tags = h("input", { type: "text", placeholder: ui("tags.input") });
  const level = h("select", null, [0, 1, 2, 3].map((l) => h("option", { value: l, selected: l === parent.variant.level }, `L${l}`)));
  const errors = h("div", { class: "form-errors" });

  const body = h("div", { class: "branch-form" },
    h("p", { class: "muted" }, ui("dynamic.parentHelp", { parent: parent.id })),
    rows,
    h("div", { class: "form-row" }, h("label", null, h("span", { class: "param-name" }, "level")), level),
    h("div", { class: "form-row" }, h("label", null, h("span", { class: "param-name" }, "note")), note),
    h("div", { class: "form-row" }, h("label", null, h("span", { class: "param-name" }, "tags")), tags),
    errors,
  );
  const submit = h("button", { class: "btn btn-primary" }, ui("build.create"));
  const modal = openModal(ui("dynamic.branchTitle", { ref: `${entity.id}@${parent.id}` }), body,
    h("div", { class: "row-between" }, changedCount, h("div", { class: "btn-group" },
      h("button", { class: "btn", onClick: () => modal.close() }, ui("common.cancel")), submit)));

  submit.addEventListener("click", async () => {
    if (submit.disabled) return;
    const invalid = body.querySelector<HTMLInputElement>("input:invalid");
    if (invalid) { invalid.reportValidity(); invalid.focus(); return; }
    const delta: Record<string, unknown> = {};
    for (const f of fields) {
      const value = f.read();
      if (typeof value === "number" && !Number.isFinite(value)) {
        errors.textContent = ui("error.number", { name: f.name });
        return;
      }
      if (!sameValue(value, params[f.name])) delta[f.name] = value;
    }
    submit.disabled = true;
    errors.textContent = "";
    try {
      const created = await api.createVariant(entity.kind, entity.id, {
        parent: parent.id,
        delta,
        note: note.value.trim(),
        tags: tags.value.split(",").map((t) => t.trim()).filter(Boolean),
        level: Number(level.value),
      });
      modal.close();
      onCreated(created.id);
    } catch (err) {
      const list = err instanceof ApiError && err.errors.length ? err.errors : [(err as Error).message];
      errors.replaceChildren(...list.map((e) => h("div", null, `✗ ${e}`)));
      submit.disabled = false;
    }
  });
  refresh();
}

function sameValue(a: unknown, b: unknown): boolean {
  if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) < 1e-9;
  return a === b;
}

function rangeHint(spec: ParamSpec): string {
  if (spec.type === "enum" || spec.type === "bool") return spec.type;
  const parts: string[] = [spec.type];
  if (spec.min != null || spec.max != null) parts.push(`${spec.min ?? "−∞"}…${spec.max ?? "∞"}`);
  return parts.join(" ");
}
