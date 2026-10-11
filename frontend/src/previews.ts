import { ui } from "./i18n";
import { h } from "./dom";

export const PROJECTION_KEYS = ["preview_front", "preview_back", "preview_right", "preview_left", "preview_top", "preview_bottom"] as const;
export type PreviewUrls = Partial<Record<typeof PROJECTION_KEYS[number] | "preview_iso" | "preview_pose" | "preview_34" | "preview_side", string>>;
const TITLES: Record<keyof PreviewUrls, string> = {
  preview_iso: ui("viewer.iso"), preview_front: ui("viewer.front"), preview_back: ui("viewer.back"),
  preview_right: ui("viewer.right"), preview_left: ui("viewer.left"), preview_top: ui("viewer.top"), preview_bottom: ui("viewer.bottom"),
  preview_pose: ui("viewer.pose"), preview_34: "3/4", preview_side: ui("viewer.side"),
};

export function renderPreviews(urls: PreviewUrls): HTMLElement {
  const keys: (keyof PreviewUrls)[] = ["preview_pose", "preview_34", "preview_iso", ...PROJECTION_KEYS];
  if (!urls.preview_right && urls.preview_side) keys.splice(5, 0, "preview_side");
  return h("div", { class: "previews projection-previews" }, keys.filter((key) => urls[key]).map((key) =>
    h("a", { href: urls[key], target: "_blank", rel: "noopener", title: ui("dynamic.openPng", { view: TITLES[key] }) },
      h("img", { src: urls[key], alt: TITLES[key], loading: "lazy", width: 512, height: 512 }),
      h("span", { class: "small" }, TITLES[key]))));
}
