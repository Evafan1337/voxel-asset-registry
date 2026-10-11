import { ui } from "../i18n";
// Reference Lab: study external character meshes (never exported to the game) next to our characters —
// topology, rig and weights of a reference, its regions, the template extracted from it, comparisons.

import { api, type LabCharacter, type RefDetail, type RefSummary, type TemplateSummary } from "../api";
import { h, mount } from "../dom";
import { LabViewer, type CompareMode, type DisplayMode, type LabMeshInfo, type LabPreset } from "../labViewer";

const DISPLAY: [DisplayMode, string][] = [["solid", ui("experimental.solid")], ["wire", ui("experimental.wireframe")], ["solidwire", ui("experimental.solidwire")],
  ["normals", ui("experimental.normals")], ["armature", ui("experimental.armature")], ["weights", ui("experimental.weights")]];
const COMPARE: [CompareMode, string][] = [["single", ui("experimental.onlyLeft")], ["side", ui("experimental.sideBySide")], ["overlay", ui("experimental.overlay")],
  ["silhouette", ui("meta.silhouette")], ["wire", ui("experimental.wires")]];
const PRESETS: [LabPreset, string][] = [["front", ui("viewer.front")], ["34", "3/4"], ["side", ui("viewer.side")], ["back", ui("viewer.back")]];
const USAGE: [string, string][] = [["visual_reference", ui("experimental.visualReference")], ["topology_study", ui("experimental.topology")],
  ["derivative_allowed", ui("experimental.derivative")], ["production_template_allowed", ui("experimental.productionTemplate")]];

interface LeftSource { key: string; label: string; url: string }

const refFile = (id: string, rel: string) => `/api/references/${id}/files/${rel}`;
const tplFile = (t: TemplateSummary, name: string) => `/api/character-templates/${t.kind}/${t.id}/${name}`;
const fmt = (n: number | undefined | null) => (n === undefined || n === null ? "—" : String(n));

function perms(usage: Record<string, boolean | undefined>): HTMLElement {
  return h("div", { class: "chips" }, USAGE.map(([k, label]) =>
    h("span", { class: `chip ${usage[k] ? "chip-ok" : "chip-off"}`, title: k }, `${usage[k] ? "✓" : "✗"} ${label}`)));
}

export async function renderReferenceLab(root: HTMLElement, refId?: string): Promise<() => void> {
  const [{ references, templates }, characters] = await Promise.all([api.references(), api.labCharacters()]);
  const current = references.find((r) => r.id === refId) ?? references[0];
  if (!current) {
    mount(root, h("div", { class: "page" }, h("h1", null, "Reference Lab"),
      h("p", { class: "muted" }, ui("experimental.noReferences"), h("code", null, "python -m registry reference import <file.blend> --id <id>"))));
    return () => undefined;
  }
  const detail: RefDetail = await api.reference(current.id);
  const ownTemplates = templates.filter((t) => t.source?.reference === detail.id);

  const sources: LeftSource[] = [
    ...(detail.models.normalized ? [{ key: "normalized", label: ui("experimental.normalized"), url: refFile(detail.id, detail.models.normalized) }] : []),
    ...(detail.models.regions ? [{ key: "regions", label: ui("experimental.regions"), url: refFile(detail.id, detail.models.regions) }] : []),
    ...ownTemplates.filter((t) => t.model).map((t) => ({ key: `tpl:${t.id}`, label: ui("experimental.templateLabel", { name: `${t.kind}/${t.id}` }), url: tplFile(t, t.model!) })),
  ];
  let left = sources.find((s) => s.key.startsWith("tpl:")) ?? sources[0];
  let right: LabCharacter | null = characters.find((c) => c.body_template !== "procedural") ?? characters[0] ?? null;
  let compare: CompareMode = "side";
  let display: DisplayMode = "solid";

  const stage = h("div", { class: "lab-stage" });
  const viewer = new LabViewer(stage);
  viewer.compare = compare;
  const meshBox = h("div", { class: "lab-meshes" });
  const meshDetail = h("div", { class: "lab-mesh-detail small" });
  const boneSelect = h("select", { class: "select-sm", title: ui("experimental.bone"),
    onChange: () => viewer.setWeightBone(boneSelect.value) });
  const opacity = h("input", { type: "range", min: "0.05", max: "1", step: "0.05", value: "0.5", class: "lab-opacity",
    title: ui("experimental.opacityHint"),
    onInput: () => viewer.setOpacity(Number(opacity.value)) });

  const leftSelect = h("select", { class: "select-sm", onChange: () => {
    left = sources.find((s) => s.key === leftSelect.value) ?? left;
    void load();
  } }, sources.map((s) => h("option", { value: s.key, selected: s.key === left?.key }, s.label)));
  const rightSelect = h("select", { class: "select-sm", onChange: () => {
    right = characters.find((c) => c.ref === rightSelect.value) ?? null;
    void load();
  } }, h("option", { value: "" }, ui("experimental.noCompare")),
  characters.map((c) => h("option", { value: c.ref, selected: c.ref === right?.ref },
    `${c.ref}${c.body_template !== "procedural" ? ` · ${c.body_template}` : " · V1"}`)));

  const compareBtns = COMPARE.map(([mode, label]) => h("button", {
    class: `btn btn-sm${mode === compare ? " active" : ""}`,
    onClick: () => {
      compare = mode;
      viewer.setCompare(mode);
      compareBtns.forEach((b, i) => b.classList.toggle("active", COMPARE[i][0] === mode));
      drawMeshes();
    },
  }, label));
  const displayBtns = DISPLAY.map(([mode, label]) => h("button", {
    class: `btn btn-sm${mode === display ? " active" : ""}`,
    onClick: () => {
      display = mode;
      viewer.setDisplay(mode);
      displayBtns.forEach((b, i) => b.classList.toggle("active", DISPLAY[i][0] === mode));
      boneSelect.hidden = mode !== "weights";
    },
  }, label));
  boneSelect.hidden = true;

  function drawMeshes(): void {
    const list = viewer.meshes();
    const row = (m: LabMeshInfo) => h("tr", { class: m.visible ? "" : "lab-hidden", onClick: () => showMesh(m) },
      h("td", { class: "mono" }, h("span", { class: `lab-dot lab-${m.side}` }), m.name),
      h("td", null, fmt(m.verts)), h("td", null, fmt(m.edges)), h("td", null, fmt(Math.round(m.tris))),
      h("td", { class: "lab-actions" },
        h("button", { class: "btn btn-sm", title: ui("experimental.isolate"), onClick: (e: Event) => { e.stopPropagation(); viewer.isolate(m.side, m.name); drawMeshes(); } }, "◉"),
        h("button", { class: "btn btn-sm", title: m.visible ? ui("common.hide") : ui("common.show"), onClick: (e: Event) => { e.stopPropagation(); viewer.toggle(m.side, m.name); drawMeshes(); } }, m.visible ? "👁" : "—"),
        h("button", { class: "btn btn-sm", title: ui("experimental.frame"), onClick: (e: Event) => { e.stopPropagation(); viewer.frameMesh(m.side, m.name); } }, "⌖")));
    mount(meshBox,
      h("div", { class: "lab-section-head" }, h("strong", null, ui("experimental.meshes")),
        h("button", { class: "btn btn-sm", onClick: () => { viewer.showAll(); drawMeshes(); } }, ui("experimental.showAll"))),
      h("table", { class: "lab-table small" },
        h("thead", null, h("tr", null, h("th", null, ui("experimental.mesh")), h("th", null, "verts"), h("th", null, "edges"), h("th", null, "tris"), h("th", null, ""))),
        h("tbody", null, list.filter((m) => m.side === "left" || compare !== "single").map(row))),
      h("div", { class: "muted small" }, ui("experimental.glbCounts")));
  }

  function showMesh(m: LabMeshInfo): void {
    mount(meshDetail,
      h("div", null, h("strong", { class: "mono" }, m.name), h("span", { class: "muted" }, m.side === "left" ? ui("experimental.leftSuffix") : ui("experimental.rightSuffix"))),
      h("div", null, `vertices ${m.verts} · edges ${m.edges} · triangles ${Math.round(m.tris)}`),
      h("div", null, ui("experimental.meshBounds", { size: m.size.map((v) => v.toFixed(3)).join(" × ") })),
      h("div", null, ui("experimental.meshMaterials", { names: m.materials.join(", ") })),
      h("div", null, m.skinned
        ? ui("experimental.meshRig", { bones: m.bones, groups: m.groups, max: m.maxInfluences })
        : ui("experimental.noArmature")),
      h("div", null, m.colors ? ui("experimental.vertexColors") : ui("experimental.noVertexColors")));
  }

  async function load(): Promise<void> {
    await viewer.setModels(left?.url ?? null, right?.model ?? null);
    viewer.setDisplay(display);
    const bones = viewer.bones();
    mount(boneSelect, bones.map((b) => h("option", { value: b }, b)));
    if (bones.length) {
      const pick = bones.includes("upper_arm.L") ? "upper_arm.L" : bones.includes("upper_armL") ? "upper_armL" : bones[0];
      boneSelect.value = pick;
      viewer.setWeightBone(pick);
    }
    drawMeshes();
    mount(meshDetail);
  }

  // ------------------------------------------------------------------ info column
  const a = detail.analysis?.analysis;
  const n = detail.analysis?.normalization;
  const analysisBox = a ? h("div", { class: "lab-card small" },
    h("div", { class: "lab-section-head" }, h("strong", null, ui("experimental.sourceAnalysis")), h("span", { class: "muted" }, `Blender ${a.file_version}`)),
    h("div", null, ui("experimental.analysisCounts", { objects: a.totals.objects, meshes: a.totals.meshes, materials: a.totals.materials })),
    h("div", null, `vertices ${a.totals.vertices} · edges ${a.totals.edges} · faces ${a.totals.faces} · triangles ${a.totals.triangles}`),
    h("div", null, `armatures ${a.totals.armatures} · bones ${a.totals.bones} · vertex groups ${a.totals.vertex_groups} · animations ${a.totals.animations}`),
    a.dimensions ? h("div", null, ui("experimental.fileBounds", { size: a.dimensions.map((v: number) => v.toFixed(3)).join(" × ") })) : null,
    a.meshes.map((m: any) => h("div", { class: "lab-sub" },
      h("span", { class: "mono" }, m.object), ` — ${m.vertices} v · ${m.faces} f (${Object.entries(m.face_sides).map(([k, v]) => `${v}×${k}-gon`).join(", ")})`,
      ui("experimental.uvGroups", { uv: m.uv_layers.length ? m.uv_layers.join(",") : ui("common.no"), groups: m.vertex_groups.length }),
      h("span", { class: m.normals?.startsWith("inward") ? "err" : "" }, m.normals ?? "?"),
      m.boundary_edges ? ui("experimental.boundaryEdges", { count: m.boundary_edges }) : "",
      m.modifiers.length ? ui("experimental.modifierList", { names: m.modifiers.map((x: any) => x.type).join(", ") }) : "")),
    n ? h("div", { class: "lab-sub" }, ui("experimental.normalization", { scale: n.scale, turn: n.turn_deg, height: n.height })) : null,
  ) : h("div", { class: "box box-info small" }, ui("experimental.noAnalysis"));

  const meta = detail.metadata as Record<string, any>;
  const permBox = h("div", { class: "lab-card small" },
    h("div", { class: "lab-section-head" }, h("strong", null, ui("experimental.rights"))),
    perms(detail.usage as Record<string, boolean>),
    h("div", null, ui("experimental.licenseValue", { name: meta.license || ui("experimental.unspecified") })),
    meta.author ? h("div", null, ui("experimental.authorValue", { name: meta.author })) : null,
    meta.source_url ? h("div", null, h("a", { href: meta.source_url, target: "_blank" }, meta.source_url)) : null,
    meta.notes ? h("div", { class: "muted" }, meta.notes) : null,
    h("div", { class: "muted" }, ui("experimental.rightsHelp")));

  const sem = detail.semantic;
  const semBox = sem ? h("div", { class: "lab-card small" },
    h("div", { class: "lab-section-head" }, h("strong", null, ui("experimental.semantics")), h("span", { class: "muted" }, "semantic.yaml")),
    h("div", { class: "chips" }, Object.entries(sem.counts).map(([k, v]) => h("span", { class: "chip" }, `${k} ${v}`))),
    h("div", null, ui("experimental.landmarkCount", { count: Object.keys(sem.landmarks).length, max: sem.max_influences })),
    detail.semantic_yaml ? h("details", null, h("summary", null, "semantic.yaml"), h("pre", { class: "lab-pre" }, detail.semantic_yaml)) : null,
  ) : h("div", { class: "box box-info small" }, ui("experimental.noSemantics"));

  const tplBox = h("div", { class: "lab-card small" },
    h("div", { class: "lab-section-head" }, h("strong", null, ui("experimental.templatesFromReference"))),
    ownTemplates.length ? ownTemplates.map((t) => h("div", { class: "lab-tpl" },
      t.preview ? h("img", { src: tplFile(t, t.preview), alt: t.id }) : null,
      h("div", null,
        h("div", null, h("strong", { class: "mono" }, `${t.kind}/${t.id}`), ui("experimental.poseValue", { name: t.pose ?? "—" })),
        h("div", null, ui("experimental.templateStats", { vertices: t.stats.vertices, faces: t.stats.faces, tris: t.stats.triangles, max: t.stats.max_influences })),
        t.extraction?.repair ? h("div", { class: "muted" },
          ui("experimental.repairCounts", { welded: t.extraction.repair.welded_vertices, filled: t.extraction.repair.filled_faces, normals: t.extraction.repair.normals ?? "—" })) : null,
        t.extraction?.support_loops?.length ? h("div", { class: "muted" },
          ui("experimental.supportLoops", { names: t.extraction.support_loops.map((l: any) => `${l.loop}.${l.side}`).join(", ") })) : null)))
      : h("div", { class: "muted" }, ui("experimental.noTemplates"), detail.id, " --id <template_id>`"));

  const gallery = h("div", { class: "lab-gallery" }, detail.previews.map((p) =>
    h("figure", null, h("img", { src: refFile(detail.id, `previews/${p}`), alt: p, loading: "lazy" }),
      h("figcaption", { class: "muted small mono" }, p.replace(".png", "")))));

  mount(root,
    h("div", { class: "page lab-page" },
      h("div", { class: "entity-head" },
        h("div", null,
          h("div", { class: "crumbs" }, h("a", { href: "#/characters" }, ui("nav.characters")), " / Reference Lab"),
          h("h1", null, "Reference Lab"),
          h("div", { class: "muted small" }, ui("experimental.referenceHelp"))),
        h("div", { class: "btn-group" }, h("a", { class: "btn btn-sm", href: "#/characters/cast" }, ui("core.cast")))),
      h("div", { class: "lab-layout" },
        h("aside", { class: "lab-list" },
          h("div", { class: "lab-section-head" }, h("strong", null, ui("experimental.references"))),
          references.map((r: RefSummary) => h("a", { class: `lab-ref${r.id === detail.id ? " active" : ""}`, href: `#/characters/lab/${r.id}` },
            r.preview ? h("img", { src: refFile(r.id, r.preview), alt: r.id }) : h("div", { class: "thumb-empty" }, r.status),
            h("div", null, h("strong", null, r.title), h("div", { class: "muted small mono" }, r.id),
              h("div", { class: "small" }, `${fmt(r.totals.vertices)} v · ${fmt(r.totals.triangles)} tris`), perms(r.usage as Record<string, boolean>)))),
          h("div", { class: "lab-section-head" }, h("strong", null, ui("experimental.templates"))),
          templates.map((t) => h("div", { class: "lab-ref" },
            t.preview ? h("img", { src: tplFile(t, t.preview), alt: t.id }) : null,
            h("div", null, h("strong", { class: "mono" }, `${t.kind}/${t.id}`),
              h("div", { class: "muted small" }, ui("experimental.templateSource", { source: t.source?.reference ?? "?", tris: t.stats.triangles })))))),
        h("main", { class: "lab-main" },
          h("div", { class: "lab-toolbar" },
            h("label", { class: "small" }, ui("viewer.left") + " ", leftSelect),
            h("div", { class: "btn-group" }, compareBtns),
            h("label", { class: "small" }, ui("viewer.right") + " ", rightSelect),
            h("label", { class: "small", title: ui("experimental.opacity") }, "α ", opacity)),
          h("div", { class: "lab-toolbar" },
            h("div", { class: "btn-group" }, displayBtns), boneSelect,
            h("div", { class: "btn-group" }, PRESETS.map(([p, label]) => h("button", { class: "btn btn-sm", onClick: () => viewer.preset(p) }, label)))),
          stage,
          h("div", { class: "muted small" }, ui("experimental.sceneHelp"),
            ui("experimental.weightsHelp")),
          gallery),
        h("aside", { class: "lab-info" }, meshBox, meshDetail, permBox, analysisBox, semBox, tplBox))));
  await load();
  const onTheme = () => viewer.applyTheme();
  window.addEventListener("themechange", onTheme);
  return () => {
    window.removeEventListener("themechange", onTheme);
    viewer.dispose();
  };
}
