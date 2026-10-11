import { LOCALES, LOCALE_NAMES, messages, type Locale, type MessageKey } from "./catalog";

export { LOCALES, LOCALE_NAMES, type Locale };
const STORAGE_KEY = "var.locale";
const OPEN = "\uE000";
const CLOSE = "\uE001";
const TOKEN = /\uE000([^\uE001]+)\uE001/g;
type Params = Record<string, string | number>;
const issuedTokens = new Map<string, { key: MessageKey; params: Params }>();
const tokenTag = `var-ui:${Math.random().toString(36).slice(2)}:`;
type Binding = { source: string; rendered: string };
const textBindings = new WeakMap<Text, Binding>();
const attributeBindings = new WeakMap<Element, Map<string, Binding>>();
const ATTRIBUTES = ["title", "label", "aria-label", "aria-description", "aria-valuetext", "aria-roledescription", "placeholder", "alt"];
let initialized = false;

/** Explicit support negotiation, not a claim that regional variants are translated. */
export function matchLocale(value: string): Locale | null {
  const tag = value.toLowerCase().replace(/_/g, "-");
  if (tag === "pt" || tag === "pt-br") return "pt-BR";
  if (["zh", "zh-hans", "zh-cn", "zh-sg"].includes(tag)) return "zh-Hans";
  if (tag.startsWith("zh-")) return null; // do not relabel Traditional Chinese as Simplified
  const language = tag.split("-")[0];
  return LOCALES.find((locale) => locale === language) ?? null;
}

export function negotiateLocale(preferences: readonly string[]): Locale {
  for (const preference of preferences) {
    const matched = matchLocale(preference);
    if (matched) return matched;
  }
  return "en";
}

function initialLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && LOCALES.includes(saved as Locale)) return saved as Locale;
  } catch { /* local storage is optional */ }
  return negotiateLocale(navigator.languages ?? [navigator.language]);
}

let locale: Locale = initialLocale();
export function getLocale(): Locale { return locale; }

export function translate(key: MessageKey, params: Params = {}, language: Locale = locale): string {
  const row = messages[key];
  if (!Object.hasOwn(messages, key)) throw new Error(`Unknown UI message: ${key}`);
  const template = row[LOCALES.indexOf(language)] || row[1] || row[0];
  return template.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g, (placeholder, name: string) => {
    const value = params[name];
    if (value === undefined) return placeholder;
    return typeof value === "number"
      ? new Intl.NumberFormat(language, { maximumFractionDigits: 4 }).format(value)
      : renderText(value, language);
  });
}

/**
 * A DOM-only token retains the source key when the locale changes. This string must
 * never be written into input.value, an API body, a recipe, a log or a clipboard.
 * Only explicit UI literals use it; user notes and registry titles are not scanned.
 */
export function ui(key: MessageKey, params: Params = {}): string {
  if (!Object.hasOwn(messages, key)) throw new Error(`Unknown UI message: ${key}`);
  const validParams: Params = {};
  for (const [name, value] of Object.entries(params)) {
    if (typeof value !== "string" && typeof value !== "number") throw new Error(`Invalid UI parameter: ${name}`);
    validParams[name] = value;
  }
  const payload = tokenTag + encodeURIComponent(JSON.stringify({ key, params: validParams }));
  issuedTokens.set(payload, { key, params: validParams });
  return `${OPEN}${payload}${CLOSE}`;
}

export function renderText(source: string, language: Locale = locale): string {
  return source.replace(TOKEN, (match, payload: string) => {
    // Literal PUA, malformed JSON and forged tokens in user notes/code stay literal.
    // Only tokens issued by the UI in this session have a translation binding.
    const issued = issuedTokens.get(payload);
    return issued ? translate(issued.key, issued.params, language) : match;
  });
}

/** Fail before fetch if a presentation token ever reaches a serialized recipe. */
export function assertNoUiTokens(value: unknown, path = "body"): void {
  if (typeof value === "string") {
    for (const match of value.matchAll(TOKEN)) {
      if (issuedTokens.has(match[1])) throw new Error(`UI label cannot be serialized at ${path}`);
    }
  } else if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoUiTokens(item, `${path}[${index}]`));
  } else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) assertNoUiTokens(item, `${path}.${key}`);
  }
}

export function formatNumber(value: number, options: Intl.NumberFormatOptions = {}): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 4, ...options }).format(value);
}

// Counts use labels with a colon instead of assuming an English plural rule.
// Expose platform plural selection for future count-specific translation entries.
export function pluralCategory(count: number, language: Locale = locale): Intl.LDMLPluralRule {
  return new Intl.PluralRules(language).select(count);
}

function localizeText(node: Text): void {
  const old = textBindings.get(node);
  if (old && node.data !== old.rendered) textBindings.delete(node);
  const binding = textBindings.get(node);
  const source = binding?.source ?? node.data;
  if (!source.includes(OPEN)) return;
  const rendered = renderText(source);
  textBindings.set(node, { source, rendered });
  if (node.data !== rendered) node.data = rendered;
}

function localizeAttributes(element: Element): void {
  let bindings = attributeBindings.get(element);
  if (!bindings) { bindings = new Map(); attributeBindings.set(element, bindings); }
  for (const attribute of ATTRIBUTES) {
    const current = element.getAttribute(attribute);
    const old = bindings.get(attribute);
    if (old && current !== old.rendered) bindings.delete(attribute);
    const source = bindings.get(attribute)?.source ?? current;
    if (!source?.includes(OPEN)) continue;
    const rendered = renderText(source);
    bindings.set(attribute, { source, rendered });
    if (current !== rendered) element.setAttribute(attribute, rendered);
  }
}

/** Update labels in place, preserving DOM identity, focus, drafts and Three.js scenes. */
export function localizeTree(root: Node): void {
  if (root instanceof Text) { localizeText(root); return; }
  if (!(root instanceof Element) && !(root instanceof DocumentFragment)) return;
  if (root instanceof Element) localizeAttributes(root);
  for (const child of root.childNodes) localizeTree(child);
}

export function setLocale(next: Locale): void {
  if (!LOCALES.includes(next)) return;
  locale = next;
  try { localStorage.setItem(STORAGE_KEY, next); } catch { /* optional */ }
  document.documentElement.lang = next;
  localizeTree(document.body);
  document.querySelectorAll<HTMLSelectElement>("[data-locale-select]").forEach((select) => { select.value = next; });
  window.dispatchEvent(new CustomEvent("localechange", { detail: next }));
}

export function initLocalization(): void {
  if (initialized) return;
  initialized = true;
  document.documentElement.lang = locale;
  localizeTree(document.body);
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "characterData") localizeTree(record.target);
      else if (record.type === "attributes") localizeAttributes(record.target as Element);
      else for (const added of record.addedNodes) localizeTree(added);
    }
  });
  observer.observe(document.body, {
    subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTES,
  });
}

const ENTITY_LABELS: Record<string, MessageKey> = {
  toon: "pack.toon",
  zuk_truck: "pack.zukTruck", mt_truck: "pack.modularTruck", evo_truck: "pack.truckEvolution",
  evo_heli_light: "pack.heliEvolution", vh_truck: "pack.truck", vh_heli_light: "pack.heli",
  td_gatling_tower: "pack.gatling", td_missile_tower: "pack.missile", td_support_tower: "pack.support",
  td_scout: "pack.scout", td_grunt: "pack.grunt", td_flyer: "pack.flyer", td_cover: "pack.cover", td_path_tile: "pack.path",
  zk_chassis: "pack.zkChassis", zk_cab: "pack.zkCab", zk_body: "pack.zkBody", zk_axle: "pack.zkAxle",
  zk_wheel: "pack.zkWheel", zk_lamp: "pack.zkLamp", zk_materials: "pack.zkMaterials",
  mt_chassis: "pack.mtChassis", mt_cabin: "pack.mtCabin", mt_cargo_box: "pack.mtCargoBox",
  mt_wheelset: "pack.mtWheelset", mt_exhaust: "pack.mtExhaust", mt_tank: "pack.mtTank", mt_toolbox: "pack.mtToolbox",
  td_base: "pack.tdBase", td_body: "pack.tdBody", td_barrel: "pack.tdBarrel", td_launcher: "pack.tdLauncher",
  td_leg: "pack.tdLeg", td_light: "pack.tdLight", td_panel: "pack.tdPanel", td_pedestal: "pack.tdPedestal",
  td_ring: "pack.tdRing", td_sensor: "pack.tdSensor", td_tower: "pack.tdTowerBase",
  td_enemy: "pack.tdEnemyBase", td_walker: "pack.tdWalkerBase", ev_plinth: "pack.evolutionPlinth",
};

/** Display-only overrides keyed by canonical ID. Unknown or authored titles stay intact. */
export function entityTitle(entity: { id: string; title?: string }): string {
  const key = ENTITY_LABELS[entity.id];
  return key ? ui(key) : entity.title || entity.id;
}

const PARAM_LABELS: Record<string, MessageKey> = {
  stage: "param.stage", part: "param.part", color: "param.color", body_color: "param.bodyColor",
  trim_color: "param.trimColor", height: "param.height", width: "param.width", length: "param.length",
  depth: "param.depth", material_preset: "param.finish", roughness: "param.roughness", metallic: "param.metallic",
  bands: "param.bands", softness: "param.softness", shadow_strength: "param.shadowStrength",
  shadow_color: "param.shadowColor", light_tint: "param.lightTint", specular: "material.specular",
  specular_size: "param.specularSize", rim: "material.rim", rim_width: "param.rimWidth", rim_color: "param.rimColor",
  halftone: "material.halftone", halftone_scale: "param.halftoneScale", outline_mode: "param.outlineMode",
  outline_width: "param.outlineWidth", outline_px: "param.outlineWidth", outline_color: "param.outlineColor",
};

export function parameterLabel(name: string): string {
  const key = PARAM_LABELS[name];
  return key ? `${ui(key)} · ${name}` : name;
}

export function translationCoverage(): Record<Locale, { translated: number; total: number }> {
  const all = Object.values(messages);
  return Object.fromEntries(LOCALES.map((language, index) => [language, {
    translated: all.filter((row) => Boolean(row[index])).length, total: all.length,
  }])) as Record<Locale, { translated: number; total: number }>;
}
