import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { registerHooks } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import test from "node:test";

// Node 22.18+ can strip these erasable TypeScript modules without another dependency.
registerHooks({
  resolve(specifier, context, nextResolve) {
    try { return nextResolve(specifier, context); }
    catch (error) {
      if (specifier.startsWith(".") && !path.extname(specifier)) return nextResolve(`${specifier}.ts`, context);
      throw error;
    }
  },
});

const { messages, LOCALES } = await import("../src/i18n/catalog.ts");
const i18n = await import("../src/i18n/index.ts");
const here = path.dirname(fileURLToPath(import.meta.url));

test("catalog has unique stable keys, EN/RU and complete core translations", () => {
  const source = readFileSync(path.join(here, "../src/i18n/catalog.ts"), "utf8");
  const rows = source.match(/const rows = `([\s\S]*?)`\.trim\(\)/)[1].trim().split("\n");
  const keys = rows.map((row) => row.split("|")[0]);
  assert.equal(new Set(keys).size, keys.length, "duplicate message key");
  assert.equal(Object.keys(messages).length, keys.length);
  for (const [key, row] of Object.entries(messages)) {
    assert.equal(row.length, LOCALES.length, key);
    assert.ok(row[0] && row[1], `EN/RU missing: ${key}`);
    if (!key.startsWith("experimental.") && !key.startsWith("legacy.")) {
      for (const language of LOCALES) assert.ok(row[LOCALES.indexOf(language)], `${language} missing: ${key}`);
    }
  }
});

test("placeholders match for every supplied language", () => {
  const placeholders = (value) => [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g)].map((m) => m[1]).sort();
  for (const [key, row] of Object.entries(messages)) {
    for (const value of row.filter(Boolean)) assert.deepEqual(placeholders(value), placeholders(row[1]), key);
  }
});

test("UI calls use catalog keys that exist", () => {
  function walk(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const filename = path.join(directory, entry.name);
      if (entry.isDirectory()) walk(filename);
      else if (filename.endsWith(".ts")) {
        const source = readFileSync(filename, "utf8");
        for (const match of source.matchAll(/\bui\("([^"\n]+)"/g)) assert.ok(Object.hasOwn(messages, match[1]), `${filename}: ${match[1]}`);
      }
    }
  }
  walk(path.join(here, "../src"));
});

test("locale negotiation handles regions, browser order and unsupported locales", () => {
  assert.equal(i18n.negotiateLocale(["de-AT", "en-US"]), "de");
  assert.equal(i18n.negotiateLocale(["ja-JP", "es-MX"]), "es");
  assert.equal(i18n.negotiateLocale(["pt-BR"]), "pt-BR");
  assert.equal(i18n.negotiateLocale(["zh-CN"]), "zh-Hans");
  assert.equal(i18n.matchLocale("zh-Hant"), null);
  assert.equal(i18n.negotiateLocale(["zh-TW", "fr-CA"]), "fr");
  assert.equal(i18n.negotiateLocale(["ar", "hi"]), "en");
});

test("nested display labels and community fallback render in all seven languages", () => {
  const title = i18n.entityTitle({ id: "mt_truck", title: "Stored authored title" });
  const token = i18n.ui("dynamic.composeTitle", { title });
  for (const language of LOCALES) {
    const rendered = i18n.renderText(token, language);
    assert.equal(/[\uE000\uE001]/u.test(rendered), false);
    assert.ok(rendered.includes(i18n.translate("pack.modularTruck", {}, language)));
  }
  assert.equal(i18n.translate("experimental.templates", {}, "de"), "Templates");
  assert.equal(i18n.entityTitle({ id: "user_thing", title: "Моя модель" }), "Моя модель");
});

test("unknown private-use text, malformed and forged tokens stay literal", () => {
  for (const raw of ["Моя заметка", "\uE000%not-json\uE001", "\uE000{bad JSON}\uE001", '\uE000{"key":"nav.assets","params":{}}\uE001']) {
    assert.equal(i18n.renderText(raw, "de"), raw);
    assert.doesNotThrow(() => i18n.assertNoUiTokens({ note: raw }));
  }
});

test("serialization guard rejects UI tokens but accepts canonical recipe data", () => {
  const recipe = { id: "v999", parent: "v001", delta: { color: "steel", stage: 3, length: 0.25 }, note: "Моя заметка" };
  const before = JSON.stringify(recipe);
  assert.doesNotThrow(() => i18n.assertNoUiTokens(recipe));
  assert.throws(() => i18n.assertNoUiTokens({ delta: { color: i18n.ui("param.color") } }), /body.delta.color/);
  assert.throws(() => i18n.assertNoUiTokens({ title: i18n.entityTitle({ id: "mt_truck" }) }), /body.title/);
  assert.equal(JSON.stringify(recipe), before);
});

test("number and plural formatting is display-only", () => {
  assert.equal(i18n.pluralCategory(1, "ru"), "one");
  assert.equal(i18n.pluralCategory(2, "ru"), "few");
  assert.equal(i18n.pluralCategory(5, "ru"), "many");
  assert.equal(i18n.pluralCategory(21, "ru"), "one");
  assert.equal(i18n.pluralCategory(2, "en"), "other");
});

test("locale changes update DOM labels and optgroup attributes without losing a draft", () => {
  class FakeNode { childNodes = []; }
  class FakeText extends FakeNode { constructor(data) { super(); this.data = data; } }
  class FakeElement extends FakeNode {
    attributes = new Map(); value = "";
    getAttribute(name) { return this.attributes.get(name) ?? null; }
    setAttribute(name, value) { this.attributes.set(name, value); }
  }
  class FakeFragment extends FakeNode {}
  globalThis.Text = FakeText;
  globalThis.Element = FakeElement;
  globalThis.DocumentFragment = FakeFragment;
  const body = new FakeElement();
  const label = new FakeText(i18n.ui("create.assetName"));
  const input = new FakeElement(); input.value = "Мой незаписанный грузовик";
  input.selectionStart = 4; input.setAttribute("placeholder", i18n.ui("create.assetName"));
  const optgroup = new FakeElement(); optgroup.setAttribute("label", i18n.ui("nav.components"));
  const note = new FakeText("\uE000%not-json\uE001 programmer_art body steel");
  body.childNodes = [label, input, optgroup, note];
  const storage = new Map();
  globalThis.localStorage = { setItem: (key, value) => storage.set(key, value) };
  globalThis.document = { body, documentElement: { lang: "en" }, querySelectorAll: () => [] };
  globalThis.window = { dispatchEvent: () => {} };
  const identity = [...body.childNodes];
  for (const language of LOCALES) {
    i18n.setLocale(language);
    assert.equal(label.data, i18n.translate("create.assetName", {}, language));
    assert.equal(input.getAttribute("placeholder"), label.data);
    assert.equal(optgroup.getAttribute("label"), i18n.translate("nav.components", {}, language));
    assert.equal(input.value, "Мой незаписанный грузовик");
    assert.equal(input.selectionStart, 4);
    assert.equal(note.data, "\uE000%not-json\uE001 programmer_art body steel");
    assert.deepEqual(body.childNodes, identity);
    assert.equal(document.documentElement.lang, language);
    assert.equal(storage.get("var.locale"), language);
  }
  // A status can reuse its node for a new message after being localized.
  label.data = i18n.ui("common.saving");
  i18n.localizeTree(body);
  i18n.setLocale("es");
  assert.equal(label.data, "Guardando…");
  // A synchronous locale change also honors writes whose observer callback has not run yet.
  label.data = i18n.ui("common.save");
  optgroup.setAttribute("label", i18n.ui("nav.assets"));
  i18n.setLocale("en");
  assert.equal(label.data, i18n.translate("common.save", {}, "en"));
  assert.equal(optgroup.getAttribute("label"), "Assets");
  label.data = "A user replaced this label";
  i18n.setLocale("ru");
  assert.equal(label.data, "A user replaced this label");
});
