# Working on Voxel Asset Registry

The source of truth is the recipe data in `registry/`. Keep changes scoped
and preserve user-authored models and references.

## Recipes and geometry

- Refine a recipe by adding a child variant. Existing variant geometry data
  is immutable; rating, tags, status and note may be updated.
- Agent-created variants use `author: llm`, `status: draft` and a note that
  explains the change. A human decides whether to approve a variant.
- When changing an entity generator, increment its `generator_version`.
  Shared geometry changes require version updates for affected generators.
- Use named palette colours. Blender axes are Z up and front -Y; interfaces
  and exported glTF use Y up and front +Z. Units are metres.
- Structural anchors use a 0.25 m grid; detail anchors use 0.0625 m. Derive
  connected geometry from shared bounds, faces, ports and sockets.
- Begin new Impressor cube-massing passes with rectangular boxes. Existing
  demonstrations may already have curved primitives in their early stages.
- Never edit or regenerate a user's manual `.blend` source. Branch from a
  procedural ancestor when a procedural refinement is requested.

## Verification

Run `python -m registry check` and relevant tests. Build changed procedural
models and inspect report checks plus front, back, left, right, top, bottom
and isometric renders. Green checks do not replace visual review.

Follow `impressor/PROJECTION_CONTRACT.md` for reference sheets. ImageGen
images are design proposals until compared with views rendered from one
3D scene. `python -m impressor sketch` prepares files only; the image tool
creates the image separately.

Do not invoke UI endpoints that open Blender on the user's desktop without
an explicit request. Keep working iterations and logs under ignored `var/`.

## Public release scope

The alpha contains the five packs declared in `release/starter-packs.yaml`
and their dependencies. Do not add external references, character body
templates or manual sources without clear redistribution terms. Keep
personal paths, credentials, local databases and user identities out of
public artifacts. Code is MIT; bundled original recipe data is CC0.
