import { ui } from "./i18n";
// Vertical variant graph: one row per variant (DFS order), elbows from parent to child.

import type { TreeNode } from "./api";
import { h, stars, statusBadge } from "./dom";

const ROW = 70;
const INDENT = 20;
const X0 = 12;
const SVG_NS = "http://www.w3.org/2000/svg";

export interface TreeOptions {
  selected: string | null;
  compare: string | null;
  onSelect: (vid: string, shift: boolean) => void;
}

interface Placed {
  node: TreeNode;
  depth: number;
  row: number;
}

function layout(nodes: TreeNode[]): Placed[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const children = new Map<string | null, TreeNode[]>();
  for (const n of nodes) {
    const parent = n.parent && byId.has(n.parent) ? n.parent : null;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent)!.push(n);
  }
  for (const list of children.values()) list.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
  const placed: Placed[] = [];
  const visit = (node: TreeNode, depth: number) => {
    placed.push({ node, depth, row: placed.length });
    for (const child of children.get(node.id) ?? []) visit(child, depth + 1);
  };
  for (const root of children.get(null) ?? []) visit(root, 0);
  return placed;
}

function svgEl<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>): SVGElementTagNameMap[K] {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  return el;
}

export function renderTree(nodes: TreeNode[], opts: TreeOptions): HTMLElement {
  const placed = layout(nodes);
  const pos = new Map(placed.map((p) => [p.node.id, p]));
  const height = placed.length * ROW;
  const maxDepth = Math.max(0, ...placed.map((p) => p.depth));

  const svg = svgEl("svg", { class: "tree-lines", width: X0 * 2 + maxDepth * INDENT + 12, height });
  const cx = (p: Placed) => X0 + p.depth * INDENT;
  const cy = (p: Placed) => p.row * ROW + ROW / 2;
  for (const p of placed) {
    const parent = p.node.parent ? pos.get(p.node.parent) : undefined;
    if (!parent) continue;
    const x0 = cx(parent);
    const y0 = cy(parent) + 7;
    const x1 = cx(p) - 7;
    const y1 = cy(p);
    const r = 8;
    svg.appendChild(svgEl("path", {
      d: `M ${x0} ${y0} V ${y1 - r} Q ${x0} ${y1} ${x0 + r} ${y1} H ${x1}`,
      class: "tree-edge",
    }));
  }
  for (const p of placed) {
    const busy = p.node.build_state === "queued" || p.node.build_state === "running";
    svg.appendChild(svgEl("circle", {
      cx: cx(p), cy: cy(p), r: 6,
      class: `tree-dot dot-${p.node.status}${busy ? " dot-busy" : ""}`,
    }));
  }

  const rows = placed.map((p) => {
    const n = p.node;
    const classes = ["tree-row"];
    if (n.id === opts.selected) classes.push("selected");
    if (n.id === opts.compare) classes.push("compare");
    if (n.status === "archived") classes.push("archived");
    const row = h("div", {
      class: classes.join(" "),
      style: `top:${p.row * ROW}px; left:${cx(p) + 12}px`,
      title: `${n.id}${n.note ? ` — ${n.note}` : ""}\n${ui("dynamic.treeHint")}`,
      role: "button", tabindex: 0,
      "data-variant": n.id,
      "aria-label": `${n.id}${n.note ? ` — ${n.note}` : ""}`,
      "aria-pressed": n.id === opts.selected || n.id === opts.compare,
      onClick: (ev: MouseEvent) => opts.onSelect(n.id, ev.shiftKey),
      onKeydown: (ev: KeyboardEvent) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          opts.onSelect(n.id, ev.shiftKey);
        }
      },
    },
      n.preview ? h("img", { class: "tree-thumb", src: n.preview, alt: n.id, loading: "lazy" }) : h("div", { class: "tree-thumb empty" }, "?"),
      h("div", { class: "tree-meta" },
        h("div", { class: "tree-line1" },
          h("strong", null, n.id),
          statusBadge(n.status, n.build_state),
          h("span", { class: "chip chip-level", title: ui("meta.levelHint") }, `L${n.level}`),
          n.author === "llm" ? h("span", { class: "chip chip-llm", title: ui("meta.llm") }, "llm") : null,
        ),
        h("div", { class: "tree-line2" }, stars(n.rating), n.error ? h("span", { class: "error-mark", title: n.error }, "⚠") : null),
        h("div", { class: "tree-note" }, n.note || " "),
      ),
    );
    return row;
  });

  return h("div", { class: "tree", style: `height:${height}px` }, svg as unknown as Node, rows);
}
