import { getLocale, initLocalization, LOCALES, LOCALE_NAMES, setLocale, ui, type Locale } from "./i18n";
import "./styles.css";

import type { Kind } from "./api";
import { h, mount, toast } from "./dom";
import { connectEvents, onBuildEvent, onConnection } from "./events";
import { APP_VERSION } from "./version";

const THEME_KEY = "var.theme";
initLocalization();
const app = document.getElementById("app")!;
const skipLink = document.querySelector(".skip-link");
if (skipLink) skipLink.textContent = ui("nav.skip");
document.querySelector(".skip-link")?.addEventListener("click", (event) => {
  event.preventDefault();
  app.focus();
});
let cleanup: (() => void) | null = null;
let renderToken = 0;
const scrollPositions = new Map<string, number>();
let currentPath = "";

// ---------------------------------------------------------------------- theme
function currentTheme(): "light" | "dark" {
  const attr = document.documentElement.dataset.theme;
  if (attr === "light" || attr === "dark") return attr;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setTheme(theme: "light" | "dark"): void {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  window.dispatchEvent(new Event("themechange"));
}

try {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
} catch { /* ignore */ }

// ---------------------------------------------------------------------- top bar
const liveDot = h("span", { class: "live-dot", title: ui("build.events") });
const queueInfo = h("span", { class: "queue-info muted small" });
const running = new Map<string, string>();

function drawTopbar(active: string): void {
  const navLink = (kind: string, label: string) => h("a", {
    href: `#/${kind}`, class: `${kind === "legacy" ? "nav-legacy " : ""}${active === kind ? "active" : ""}`,
    "aria-current": active === kind ? "page" : undefined,
  }, label);
  mount(document.getElementById("topbar")!,
    h("a", { class: "brand", href: "#/" }, h("span", { class: "brand-mark" }, "◆"), "Voxel Asset Registry",
      h("span", { class: "small muted app-version" }, APP_VERSION)),
    h("nav", { "aria-label": ui("nav.sections") },
      navLink("components", ui("nav.components")), navLink("assets", ui("nav.assets")),
      navLink("materials", ui("nav.materials")), navLink("characters", ui("nav.characters")), navLink("legacy", "Legacy"),
    ),
    h("div", { class: "topbar-right" },
      queueInfo, liveDot,
      h("label", { class: "locale-control", title: ui("nav.language") }, "🌐",
        h("select", {
          class: "select-sm", "aria-label": ui("nav.language"), "data-locale-select": "true",
          onChange: (event: Event) => setLocale((event.target as HTMLSelectElement).value as Locale),
        }, LOCALES.map((language) => h("option", { value: language, selected: language === getLocale() }, LOCALE_NAMES[language])))),
      h("button", { class: "btn btn-ghost", title: ui("nav.themeHint"),
        onClick: () => setTheme(currentTheme() === "dark" ? "light" : "dark") }, ui("nav.theme")),
      h("a", { class: "btn btn-ghost", href: `/guide/${getLocale()}.html`, "data-localized-guide": "true",
        target: "_blank", rel: "noopener" }, ui("nav.guide")),
      h("a", { class: "btn btn-ghost", href: "/docs", target: "_blank", rel: "noopener", title: "OpenAPI" }, "API"),
    ),
  );
}

function drawQueue(): void {
  queueInfo.textContent = running.size ? ui("build.queue", { count: running.size }) : "";
}

onConnection((online) => {
  liveDot.classList.toggle("online", online);
  liveDot.title = online ? ui("build.connected") : ui("build.reconnecting");
});
onBuildEvent((ev) => {
  if (ev.type !== "build" || !ev.hash) return;
  if (ev.state === "queued" || ev.state === "running") running.set(ev.hash, ev.state);
  else running.delete(ev.hash);
  drawQueue();
});

// ---------------------------------------------------------------------- router
async function route(): Promise<void> {
  const token = ++renderToken;
  if (currentPath) scrollPositions.set(currentPath, app.scrollTop);
  cleanup?.();
  cleanup = null;
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, qs] = raw.split("?");
  const query = new URLSearchParams(qs ?? "");
  const parts = path.split("/").filter(Boolean);
  const kind: Kind = parts[0] === "assets" ? "assets" : parts[0] === "materials" ? "materials"
    : parts[0] === "characters" ? "characters" : "components";
  currentPath = path || "components";
  drawTopbar(parts[0] === "blockout" ? "components" : parts[0] || "components");
  // Each render owns its container. A slow previous route cannot overwrite the current page.
  const root = h("div", { class: "route-root", "aria-busy": "true" },
    h("div", { class: "loading", role: "status" }, ui("common.loading")));
  mount(app, root);
  app.scrollTop = 0;
  try {
    let dispose: () => void;
    if (parts[0] && !["components", "assets", "materials", "characters", "legacy", "blockout"].includes(parts[0])) {
      throw new Error(ui("error.route"));
    }
    if (parts[0] === "blockout") {
      if (!parts[1] || parts.length !== 2) throw new Error(ui("blockout.noGroup"));
      const page = await import("./pages/blockoutSheet");
      if (token !== renderToken) return;
      dispose = await page.renderBlockoutSheet(root, decodeURIComponent(parts[1]), query);
    } else if (parts[0] === "legacy") {
      const page = await import("./pages/legacy");
      if (token !== renderToken) return;
      dispose = parts[1] ? await page.renderLegacyItem(root, parts[1]) : await page.renderLegacy(root);
    } else if (parts.length <= 1) {
      const page = await import("./pages/registry");
      if (token !== renderToken) return;
      dispose = await page.renderRegistry(root, kind);
    } else if (parts[0] === "assets" && parts[1] === "new") {
      const page = await import("./pages/createAsset");
      if (token !== renderToken) return;
      dispose = await page.renderCreateAsset(root);
    } else if (parts[0] === "characters" && parts[1] === "cast") {
      const page = await import("./pages/cast");
      if (token !== renderToken) return;
      dispose = await page.renderCast(root);
    } else if (parts[0] === "characters" && parts[1] === "lab") {
      const page = await import("./pages/referenceLab");
      if (token !== renderToken) return;
      dispose = await page.renderReferenceLab(root, parts[2]);
    } else if (parts[0] === "assets" && parts[2] === "compose") {
      const page = await import("./pages/compose");
      if (token !== renderToken) return;
      dispose = await page.renderCompose(root, parts[1], query);
    } else if (parts[0] === "assets" && parts[2] === "edit") {
      const page = await import("./pages/edit");
      if (token !== renderToken) return;
      dispose = await page.renderEdit(root, parts[1], query);
    } else if (kind === "materials") {
      const page = await import("./pages/material");
      if (token !== renderToken) return;
      dispose = await page.renderMaterial(root, parts[1], query);
    } else {
      const page = await import("./pages/entity");
      if (token !== renderToken) return;
      dispose = await page.renderEntity(root, kind, parts[1], query);
    }
    if (token !== renderToken) dispose();
    else {
      cleanup = dispose;
      root.setAttribute("aria-busy", "false");
      app.scrollTop = scrollPositions.get(currentPath) ?? 0;
    }
  } catch (err) {
    if (token !== renderToken) return;
    root.setAttribute("aria-busy", "false");
    mount(root, h("div", { class: "page route-error", role: "alert" }, h("h2", null, ui("error.page")),
      h("p", { class: "error" }, (err as Error).message),
      h("div", { class: "actions" }, h("button", { class: "btn btn-primary", onClick: () => void route() }, ui("common.retry")),
        h("a", { class: "btn", href: "#/" }, ui("nav.backRegistry")))));
    toast((err as Error).message, "error");
  }
}

window.addEventListener("hashchange", () => void route());
window.addEventListener("localechange", () => {
  document.querySelectorAll<HTMLAnchorElement>("[data-localized-guide]").forEach((link) => { link.href = `/guide/${getLocale()}.html`; });
});
connectEvents();
void route();
