import { ui } from "../i18n";
// Character cast: every member of registry/characters/cast.yaml in one scene, one camera,
// one material and the same clip on everyone — does the cast read as one game?

import { api, type CastMember } from "../api";
import { h, mount } from "../dom";
import { ViewerPanel } from "../viewerPanel";

const CLIPS = ["idle", "walk", "talk", "work", "celebrate"];

export async function renderCast(root: HTMLElement): Promise<() => void> {
  const cast = await api.characterCast();
  const panel = new ViewerPanel("", { materialSelect: true });
  const ready = cast.members.filter((m) => m.model);
  const missing = cast.members.filter((m) => !m.model);
  let clip = "idle";

  const clipButtons = CLIPS.map((name) => h("button", {
    class: "btn btn-sm" + (name === clip ? " active" : ""),
    onClick: () => {
      clip = name;
      panel.setClip(name);
      clipButtons.forEach((b, i) => b.classList.toggle("active", CLIPS[i] === name));
    },
  }, name));

  const member = (m: CastMember) => h("a", { class: "cast-member", href: `#/characters/${m.id}?v=${m.vid}` },
    m.preview ? h("img", { src: m.preview, alt: m.ref, loading: "lazy" }) : h("div", { class: "thumb-empty" }, m.build_state),
    h("div", { class: "small" }, h("strong", null, m.title), h("div", { class: "muted mono" }, m.ref)),
    m.error ? h("div", { class: "error small" }, m.error) : null);

  mount(root,
    h("div", { class: "page cast-page" },
      h("div", { class: "entity-head" },
        h("div", null,
          h("div", { class: "crumbs" }, h("a", { href: "#/characters" }, ui("nav.characters")), ui("experimental.castBreadcrumb")),
          h("h1", null, cast.title),
          h("div", { class: "muted small" }, cast.note, ui("experimental.castSource"))),
        h("div", { class: "btn-group" }, clipButtons)),
      h("div", { class: "cast-stage" }, panel.el),
      missing.length ? h("div", { class: "box box-info small" },
        ui("experimental.castMissing"), missing.map((m) => m.ref).join(", "), ui("experimental.castSkipped")) : null,
      h("div", { class: "cast-members" }, cast.members.map(member)),
    ));
  await panel.showMany(ready.map((m) => m.model!), { preset: "34", clip }, cast.spacing);
  return () => panel.dispose();
}
