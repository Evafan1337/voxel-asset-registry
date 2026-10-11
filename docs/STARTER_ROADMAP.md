# Public alpha roadmap

The first alpha focuses on local procedural authoring: five starter packs,
reproducible source installation, seven interface locales, Impressor briefs
and models that can be rebuilt from public recipes.

## Maintain a reproducible release

Keep the pack manifest and dependency closure explicit. Add regression
coverage for installation, recipe resolution and failure reporting before
expanding the catalogue. Verify generated screenshots and release artifacts
from a clean public checkout. Linux is the initial supported setup;
Windows/macOS wrappers and container delivery need their own validation.

## Improve language coverage

Review EN/RU workflows end to end and invite native speakers to refine ES,
PT-BR, Simplified Chinese, FR and DE. Display metadata needs a separate
translation layer keyed by canonical entity/parameter IDs. Recipes, sockets,
user notes and geometry hashes must remain independent of the UI language.

## Separate materials from rendering style

Current tools provide a named palette, surface properties, finish presets,
generated albedo/ORM textures and toon rendering. The next useful step is a
physical surface catalogue with base colour, roughness, metallic, emission
and explicit opacity settings, separate from toon light bands and outlines.

Assign finishes by semantic role such as body, glass, tyre, rim and hardware.
An asset look should override those roles without changing geometry or
component recipes. Later work can add wear, texture resolution budgets and
UV conventions with matching Blender/browser/Godot checks. These are future
format and UI changes, not supported fields to add to today's recipes.

## Extend Impressor without hiding provenance

Continue the brief → reference proposal → box massing → refinement → verified
asset cycle. Keep input images, prompts, accepted decisions and all rendered
views traceable. An optional image-provider adapter can be added later with
explicit configuration; image generation is currently performed by an
image-capable agent outside the local CLI.
