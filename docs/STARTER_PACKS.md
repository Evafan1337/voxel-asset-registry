# Using the starter packs

Start with one model, build it, then compare its stages. The public catalogue
contains complete parent recipes and components so every included reference
can resolve independently of the author's working collection.

| Pack | Suggested first reference | Next comparison |
| --- | --- | --- |
| `zuk_truck` | `assets/zuk_truck/v009` | `v010`, `v011`, then the arch alternative `v012` |
| `td` | `assets/td_gatling_tower/v002` | Missile/support towers and scout/grunt/flyer enemies |
| `mt_truck` | `assets/mt_truck/v001` | `v002` through `v005` |
| `evo_truck` | `components/vh_truck/v001` | Individual stages `v002`–`v005`, then the exhibition asset |
| `evo_heli_light` | `components/vh_heli_light/v001` | Individual stages `v002`–`v005`, then the exhibition asset |

`evo_*` assets are exhibitions on plinths. Use the individual `vh_*` component
models for a game vehicle. Existing early demonstrations may contain curved
primitives; a new strict Impressor cube-massing pass uses boxes only.

## Build a pack

```bash
.venv/bin/python -m registry build-demo --pack zuk_truck
.venv/bin/python -m registry build-demo --pack td
.venv/bin/python -m registry build-demo --pack mt_truck
.venv/bin/python -m registry build-demo --pack evo_truck
.venv/bin/python -m registry build-demo --pack evo_heli_light
```

Running `build-demo` without a pack builds ten introductory targets including
the full models used by the toon material preview. `--list` validates and
prints the targets without launching Blender.

## Review and refine

Inspect the report and seven real views. Check wheel/leg contact, supports,
silhouette and intersections before adding detail. Use a new child variant
to change one parameter or attachment. Keep technical IDs and socket names
unchanged when switching the interface language.

The optional starter-model ZIP contains 29 GLBs with seven PNG projections
per model. Its `index.json` records canonical references and SHA-256 digests.
It contains no build logs, absolute recipe paths or private source files.
Source recipes remain in the main repository; the ZIP is for inspection and
direct import. Included original model content is CC0.

See [the pipeline guide](guide/en.html), [the projection contract](../impressor/PROJECTION_CONTRACT.md)
and [the release manifest](../release/starter-packs.yaml).
