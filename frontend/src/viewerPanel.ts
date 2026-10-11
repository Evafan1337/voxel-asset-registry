import { ui } from "./i18n";
// Viewer + toolbar + info overlay + animation controls.

import { api, type MaterialPreset } from "./api";
import { h, mount } from "./dom";
import { toToonParams } from "./toon";
import { Viewer, type LayoutModel, type ModelMeta, type ViewerOptions, type ViewPreset } from "./viewer";

const MATERIAL_KEY = "var.viewer.material";
let presetsPromise: Promise<MaterialPreset[]> | null = null;

/** Material presets (cached; call refreshPresets() after creating material variants). */
export function materialPresets(): Promise<MaterialPreset[]> {
  presetsPromise ??= api.materialPresets().catch(() => []);
  return presetsPromise;
}

export function refreshPresets(): void {
  presetsPromise = null;
}

const OPTIONS_KEY = "var.viewer.options";

function loadOptions(): ViewerOptions {
  const defaults: ViewerOptions = { wireframe: false, grid: false, sockets: false, collision: false, autoRotate: false,
    skeleton: false };
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(OPTIONS_KEY) ?? "{}");
    if (saved && typeof saved === "object") {
      for (const key of Object.keys(defaults) as (keyof ViewerOptions)[]) {
        const value = (saved as Record<string, unknown>)[key];
        if (typeof value === "boolean") defaults[key] = value;
      }
    }
    return defaults;
  } catch {
    return defaults;
  }
}

function saveOptions(options: ViewerOptions): void {
  try {
    localStorage.setItem(OPTIONS_KEY, JSON.stringify(options));
  } catch {
    /* storage unavailable */
  }
}

const PRESETS: [ViewPreset, string][] = [["iso", ui("viewer.iso")], ["34", "3/4"], ["front", ui("viewer.front")], ["side", ui("viewer.side")], ["top", ui("viewer.top")]];
const TOGGLES: [keyof ViewerOptions, string, string][] = [
  ["autoRotate", "⟳", ui("viewer.autoRotate")],
  ["wireframe", ui("viewer.wireframe"), "Wireframe"],
  ["grid", ui("viewer.bounds"), ui("viewer.gridHint")],
  ["sockets", ui("viewer.sockets"), ui("viewer.showSockets")],
  ["collision", ui("viewer.collision"), ui("viewer.showCollision")],
  ["skeleton", ui("viewer.skeleton"), ui("viewer.showBones")],
];

export class ViewerPanel {
  readonly el: HTMLElement;
  readonly viewer: Viewer;
  private stage: HTMLElement;
  private info: HTMLElement;
  private anim: HTMLElement;
  private aim: HTMLElement;
  private caption: HTMLElement;
  private status: HTMLElement;
  private toggleButtons = new Map<keyof ViewerOptions, HTMLButtonElement>();
  onOptionChange: ((key: keyof ViewerOptions, value: boolean) => void) | null = null;

  private materialSelect: HTMLSelectElement | null = null;
  private shown: { urls: string[]; meta: ModelMeta; spacing: number; layout?: LayoutModel[] } | null = null;
  private disposed = false;
  private showToken = 0;
  private materialToken = 0;

  constructor(caption = "", opts: { materialSelect?: boolean; editor?: boolean } = {}) {
    this.stage = h("div", { class: "viewer-stage" });
    this.info = h("div", { class: "viewer-info" });
    this.anim = h("div", { class: "viewer-anim" });
    this.aim = h("div", { class: "viewer-aim" });
    this.caption = h("div", { class: "viewer-caption" }, caption);
    this.status = h("div", { class: "viewer-status", role: "status", "aria-live": "polite", hidden: true });
    const toolbar = h("div", { class: "viewer-toolbar" },
      h("div", { class: "btn-group" },
        PRESETS.map(([name, label]) => h("button", { class: "btn btn-sm", onClick: () => this.viewer.preset(name) }, label)),
        h("button", { class: "btn btn-sm", title: ui("viewer.reset"), onClick: () => this.viewer.reset() }, "⟲"),
      ),
      h("div", { class: "btn-group" },
        TOGGLES.filter(([key]) => !opts.editor || (key !== "collision" && key !== "autoRotate")).map(([key, label, title]) => {
          const btn = h("button", { class: "btn btn-sm btn-toggle", title, "aria-label": title, onClick: () => this.toggle(key) }, label);
          this.toggleButtons.set(key, btn);
          return btn;
        }),
        opts.materialSelect === false ? null : (this.materialSelect = h("select", {
          class: "select-sm", title: ui("viewer.materialHint"),
          onChange: () => void this.applySelectedMaterial(true),
        }, h("option", { value: "" }, "PBR"))),
      ),
    );
    this.el = h("div", { class: "viewer-panel" }, toolbar, this.aim, h("div", { class: "viewer-body" }, this.stage, this.caption, this.status, this.info, this.anim));
    this.viewer = new Viewer(this.stage);
    this.viewer.onAnimationFinished = () => {
      const button = this.anim.querySelector("button");
      if (button) { button.textContent = "▶"; button.title = ui("viewer.replay"); button.setAttribute("aria-label", button.title); }
    };
    this.viewer.onContextLost = () => this.setStatus(ui("viewer.webglLost"));
    this.viewer.onContextRestored = () => {
      if (this.shown?.layout) void this.showLayout(this.shown.layout, this.shown.meta);
      else if (this.shown) void this.showMany(this.shown.urls, this.shown.meta, this.shown.spacing);
    };
    this.viewer.options = loadOptions();
    if (opts.editor) this.viewer.options = { ...this.viewer.options, grid: false, collision: false, autoRotate: false };
    this.viewer.setOption("grid", this.viewer.options.grid);
    this.viewer.setOption("collision", this.viewer.options.collision);
    this.syncToggleButtons();
    if (this.materialSelect) void this.fillMaterials();
  }

  private async fillMaterials(): Promise<void> {
    const select = this.materialSelect!;
    const presets = await materialPresets();
    if (this.disposed) return;
    let saved = "";
    try { saved = localStorage.getItem(MATERIAL_KEY) ?? ""; } catch { /* ignore */ }
    for (const p of presets) {
      select.appendChild(h("option", { value: p.ref, selected: p.ref === saved }, `${p.ref}${p.note ? ` · ${p.note.slice(0, 28)}` : ""}`));
    }
    await this.applySelectedMaterial(false);
  }

  private async applySelectedMaterial(remember: boolean): Promise<void> {
    if (this.disposed) return;
    const token = ++this.materialToken;
    const ref = this.materialSelect?.value ?? "";
    if (remember) {
      try { localStorage.setItem(MATERIAL_KEY, ref); } catch { /* ignore */ }
    }
    const preset = (await materialPresets()).find((p) => p.ref === ref);
    if (this.disposed || token !== this.materialToken) return;
    this.viewer.setMaterial(preset ? toToonParams(preset.params) : null);
  }

  private toggle(key: keyof ViewerOptions): void {
    const value = !this.viewer.options[key];
    this.setOption(key, value);
    this.onOptionChange?.(key, value);
  }

  setOption(key: keyof ViewerOptions, value: boolean): void {
    this.viewer.setOption(key, value);
    saveOptions(this.viewer.options);
    this.syncToggleButtons();
  }

  private syncToggleButtons(): void {
    for (const [key, btn] of this.toggleButtons) {
      btn.classList.toggle("active", this.viewer.options[key]);
      btn.setAttribute("aria-pressed", String(this.viewer.options[key]));
    }
  }

  setCaption(text: string): void {
    this.caption.textContent = text;
  }

  setStatus(text: string): void {
    this.status.textContent = text;
    this.status.hidden = !text;
  }

  async show(url: string | null, meta: ModelMeta): Promise<boolean> {
    return this.showMany(url ? [url] : [], meta);
  }

  async showLayout(items: LayoutModel[], meta: ModelMeta): Promise<boolean> {
    const layout = items.map((item) => ({ ...item, position: [...item.position] as LayoutModel["position"] }));
    return this.showMany(layout.map((item) => item.url), { animate: false, ...meta }, 0, layout);
  }

  /** Several models in one scene (the character cast); one clip selector drives all of them. */
  async showMany(urls: string[], meta: ModelMeta, spacing = 1.35, layout?: LayoutModel[]): Promise<boolean> {
    if (this.disposed) return false;
    const token = ++this.showToken;
    this.shown = urls.length ? { urls: [...urls], meta: { ...meta }, spacing, layout } : null;
    mount(this.info);
    mount(this.anim);
    mount(this.aim);
    if (!urls.length) {
      this.viewer.clear();
      this.setStatus(layout ? ui("viewer.noParts") : ui("build.noBuiltModel"));
      return false;
    }
    this.setStatus(ui("common.loading"));
    try {
      const info = layout ? await this.viewer.loadLayout(layout, meta) : await this.viewer.loadMany(urls, meta, spacing);
      if (this.disposed || token !== this.showToken) return false;
      this.setStatus("");
      const s = info.size;
      const v = info.voxels;
      mount(this.info,
        h("span", null, `${Math.round(info.tris)} tris`),
        h("span", null, `${info.verts} verts`),
        h("span", null, `${s.x.toFixed(2)} × ${s.y.toFixed(2)} × ${s.z.toFixed(2)} m`),
        h("span", null, `${fmtVox(v.x)} × ${fmtVox(v.y)} × ${fmtVox(v.z)} vox`),
      );
      if (info.clips.length) this.renderAnimControls(info.clips, meta.clip);
      if (!layout && info.aim?.length) this.renderAimControls(info.aim);
      return true;
    } catch (err) {
      if (!this.disposed && token === this.showToken && (err as Error).message !== "superseded") {
        this.setStatus(ui("dynamic.glbError", { error: err instanceof Error ? err.message : String(err) }));
      }
      return false;
    }
  }

  /** Play `name` and keep the clip selector in step (the cast page drives all members at once). */
  setClip(name: string): void {
    this.viewer.play(name);
    const select = this.anim.querySelector("select");
    if (select) select.value = name;
    const button = this.anim.querySelector("button");
    if (button) {
      const playing = this.viewer.isPlaying();
      button.textContent = playing ? "❚❚" : "▶";
      button.title = playing ? ui("viewer.pause") : ui("viewer.play");
      button.setAttribute("aria-label", button.title);
    }
  }

  private renderAnimControls(clips: string[], current?: string): void {
    const playing = this.viewer.isPlaying();
    const title = playing ? ui("viewer.pause") : ui("viewer.play");
    const playBtn = h("button", { class: "btn btn-sm", title, "aria-label": title }, playing ? "❚❚" : "▶");
    playBtn.addEventListener("click", () => {
      const playing = this.viewer.togglePlay();
      playBtn.textContent = playing ? "❚❚" : "▶";
      playBtn.title = playing ? ui("viewer.pause") : ui("viewer.play");
      playBtn.setAttribute("aria-label", playBtn.title);
    });
    const select = h("select", { class: "select-sm", onChange: (ev: Event) => {
      this.viewer.play((ev.target as HTMLSelectElement).value);
      playBtn.textContent = "❚❚";
      playBtn.title = ui("viewer.pause");
      playBtn.setAttribute("aria-label", playBtn.title);
    }, "aria-label": ui("viewer.clip") }, clips.map((c) => h("option", { value: c, selected: c === current }, c)));
    mount(this.anim, h("span", { class: "muted" }, ui("viewer.animation")), select, playBtn);
  }

  private renderAimControls(joints: NonNullable<import("./viewer").ViewerInfo["aim"]>): void {
    mount(this.aim, h("span", { class: "muted small" }, ui("viewer.aim")),
      joints.map((joint) => {
        const value = h("output", { class: "mono small" }, `${joint.value}°`);
        const input = h("input", { type: "range", min: joint.min, max: joint.max, step: 1, value: joint.value,
          "aria-label": joint.axis === "yaw" ? ui("viewer.yaw") : ui("viewer.pitch"),
          onInput: (event: Event) => {
            const angle = Number((event.target as HTMLInputElement).value);
            this.viewer.setAim(joint.axis, angle);
            value.textContent = `${angle}°`;
            const play = this.anim.querySelector("button");
            if (play) { play.textContent = "▶"; play.title = ui("viewer.play"); play.setAttribute("aria-label", play.title); }
          } });
        return h("label", { class: "viewer-aim-control" }, joint.axis === "yaw" ? ui("viewer.rotation") : ui("viewer.elevation"), input, value);
      }), h("span", { class: "muted small" }, ui("viewer.aimHelp")));
  }

  applyTheme(): void {
    this.viewer.applyTheme();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.showToken++;
    this.materialToken++;
    this.shown = null;
    this.viewer.dispose();
    this.el.remove();
  }
}

function fmtVox(n: number): string {
  return Math.abs(n - Math.round(n)) < 0.01 ? String(Math.round(n)) : n.toFixed(1);
}
