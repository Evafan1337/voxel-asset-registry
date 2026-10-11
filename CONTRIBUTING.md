# Contributing to Voxel Asset Registry

Start with a small reproducible change. Useful alpha contributions include
installation fixes, clearer error messages, native-language review and
procedural examples that demonstrate one modelling decision.

## Set up

Use Node.js 24 for development. The frontend regression runner needs Node
22.18+; the supported installation versions in README also cover users who
only build and run the application.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

Run `./run.sh --dev` to work on the API and interface. Keep local executable
paths in `config.local.yaml`. Generated models, databases and image
iterations belong under ignored `build/` and `var/`.

## Validate changes

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m registry check
.venv/bin/python -m registry build-demo --list
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Use Blender to rebuild models affected by geometry changes. Inspect all
seven standard views and the report. Include the relevant commands and
results in your pull request; say which external tool checks you ran.

## Recipes and translations

Add a child variant when refining a model. Describe its purpose and keep it
`draft` until human review. See [AGENTS.md](AGENTS.md) for geometry rules.

Translate interface labels and display metadata, preserving canonical
IDs, enum values, socket names and recipes. Check that a language change
preserves an unsaved form. EN/RU are the primary alpha review languages;
native speakers can improve the other five locales.

## Licensing and bug reports

Code contributions follow MIT. Original starter recipe/model contributions
follow CC0; include provenance and do not submit third-party content under
terms you cannot grant. Never attach credentials or private workspaces.

For a bug, include the version, operating system, tool versions, commands,
expected behaviour and the relevant report checks. Remove personal paths
and sensitive information from attached logs. Large feature ideas can be
discussed in an issue before implementation.
