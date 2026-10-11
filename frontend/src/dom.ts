import { localizeTree, ui } from "./i18n";
// Tiny DOM helpers — the UI is plain TypeScript without a framework.

export type Child = Node | string | number | null | undefined | false | Child[];
type Handler = (ev: any) => void;
export type Props = Record<string, unknown> & { class?: string; style?: string };

const PROPERTY_KEYS = new Set(["value", "checked", "disabled", "selected", "hidden", "title", "min", "max", "step"]);

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props?: Props | null,
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null) continue;
      // ARIA false is meaningful; boolean DOM properties must also keep their false value.
      if (value === false && !PROPERTY_KEYS.has(key) && !key.startsWith("aria-")) continue;
      if (key.startsWith("on") && typeof value === "function") {
        el.addEventListener(key.slice(2).toLowerCase(), value as Handler);
      } else if (key === "class") {
        el.className = String(value);
      } else if (key === "style") {
        el.setAttribute("style", String(value));
      } else if (PROPERTY_KEYS.has(key)) {
        (el as any)[key] = value;
      } else {
        el.setAttribute(key, value === true && !key.startsWith("aria-") ? "" : String(value));
      }
    }
  }
  append(el, children);
  localizeTree(el);
  return el;
}

export function append(el: Node, children: Child[]): void {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    if (Array.isArray(child)) append(el, child);
    else el.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(el: Element): void {
  while (el.firstChild) el.removeChild(el.firstChild);
}

export function mount(el: Element, ...children: Child[]): void {
  clear(el);
  append(el, children);
}

export function toast(message: string, kind: "info" | "ok" | "error" = "info", ms = 3500): void {
  const host = document.getElementById("toasts");
  if (!host) return;
  const node = h("div", { class: `toast toast-${kind}` }, message);
  node.setAttribute("role", kind === "error" ? "alert" : "status");
  host.appendChild(node);
  window.setTimeout(() => node.classList.add("toast-hide"), ms);
  window.setTimeout(() => node.remove(), ms + 400);
}

export function fmtValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(+value.toFixed(4));
  if (typeof value === "boolean") return value ? ui("common.yes") : ui("common.no");
  return String(value);
}

export function stars(rating: number | null, onPick?: (value: number | null) => void): HTMLElement {
  const wrap = h("span", { class: `stars${onPick ? " stars-edit" : ""}`, title: rating ? ui("dynamic.rating", { value: rating }) : ui("entity.noRating") });
  for (let i = 1; i <= 5; i++) {
    const star = onPick
      ? h("button", { type: "button", class: `star${rating && i <= rating ? " on" : ""}`,
        "aria-label": rating === i ? ui("entity.removeRating") : ui("dynamic.setRating", { value: i }), "aria-pressed": rating === i }, "★")
      : h("span", { class: `star${rating && i <= rating ? " on" : ""}` }, "★");
    if (onPick) star.addEventListener("click", (ev) => {
      ev.stopPropagation();
      onPick(rating === i ? null : i);
    });
    wrap.appendChild(star);
  }
  return wrap;
}

export const STATUS_LABEL: Record<string, string> = {
  draft: ui("status.draft"),
  built: ui("status.built"),
  failed: ui("status.failed"),
  approved: ui("status.approved"),
  archived: ui("status.archived"),
};

export function statusBadge(status: string, buildState?: string): HTMLElement {
  const busy = buildState === "queued" || buildState === "running";
  return h(
    "span",
    { class: `badge badge-${status}${busy ? " badge-busy" : ""}`, title: busy ? ui("dynamic.buildState", { state: buildState ?? "" }) : status },
    busy ? (buildState === "queued" ? ui("status.queued") : ui("status.running")) : STATUS_LABEL[status] ?? status,
  );
}

export function debounce<T extends unknown[]>(fn: (...args: T) => void, ms: number): ((...args: T) => void) & { cancel: () => void } {
  let timer = 0;
  const debounced = (...args: T) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), ms);
  };
  debounced.cancel = () => window.clearTimeout(timer);
  return debounced;
}
