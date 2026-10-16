# Changelog

## 0.1.0-alpha.2

- New `steam_engine` starter pack: three presets of an animated cut-away mill
  engine (`components/mx_steam_engine/v001`–`v003`), with GLB, projections and
  `.blend` downloads like the other starter models.
- The engine's moving parts keep clear through the whole `work` loop: the
  conrod passes between the guide bars, the piston stops short of the covers
  and the valve chest, the crankshaft stays inside the eccentric sheave.
- `builder/motion_clearance.py` checks rigid moving parts for crossings in
  every frame of a built GLB (headless Blender); `tests/test_motion_clearance.py`
  runs it on the steam engine when Blender and the builds are available.

## 0.1.0-alpha.1

- Curated five-pack starter collection with complete recipe inheritance and
  component dependencies.
- Reproducible source installation, tool diagnostics and selected demo
  builds with failure exit codes.
- Seven interface locales and offline pipeline documentation.
- Impressor prompt preparation and a six-projection plus isometric contract.
- Durable unexpected build failures and resilient event subscribers.
- Toon previews tied to explicit starter model variants.
- Fresh public packaging with separate software and demo content licenses.

Initial platform: Linux. Godot export is optional. Image generation requires
an external image-capable agent. Technical build results remain separate
from human model approval.
