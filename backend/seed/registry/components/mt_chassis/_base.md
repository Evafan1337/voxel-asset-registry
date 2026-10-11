---
id: mt_chassis
title: Модульный грузовик · шасси
type: structure
category: truck_kit
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular]
interface:
  grid_size: [10, 4, 32]
  voxel_size: 0.25
  pivot: ground
  mounts: []
  sockets:
    - {name: cab, type: generic, position: [0.0, 0.0, 2.75], description: "Под передней гранью кабины"}
    - {name: box, type: generic, position: [0.0, 0.0, -1.5], description: "Под центром фургона"}
    - {name: axle_front, type: generic, position: [0.0, 0.0, 3.25], description: "Под передней осью"}
    - {name: axle_rear_1, type: generic, position: [0.0, 0.0, -1.75], description: "Под первой задней осью"}
    - {name: axle_rear_2, type: generic, position: [0.0, 0.0, -3.0], description: "Под второй задней осью"}
    - {name: exhaust, type: generic, position: [1.0, 0.0, 1.0], description: "Под выхлопной трубой (левый борт)"}
    - {name: tank, type: generic, position: [0.75, 0.0, 0.25], description: "Под баком (левый борт)"}
    - {name: toolbox, type: generic, position: [0.75, 0.0, -0.75], description: "Под ящиком (левый борт)"}
design_intent:
  role: chassis
  purpose: "Рама, на которую по сокетам садятся все блоки набора"
  primary_parts: [chassis]
  secondary_parts: []
  relationships: []
  forbidden: [orphan_geometry]
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME (материалы)"}
---
Шасси модульного грузовика (набор `mt_`, общий скелет — `builder/trucklib.py`). Рама с
лонжеронами, рессорами над тремя осями, поперечинами, задним брусом с фонарями и брызговиками.

Сокеты — якоря набора на дороге (z = 0) под точкой крепления каждого блока: `cab`, `box`,
`axle_front`, `axle_rear_1`, `axle_rear_2`, `exhaust`, `tank`, `toolbox`. Блоки строятся в высотах
грузовика вокруг того же якоря (`vehlib.render(plan, origin=...)`), поэтому садятся без смещений.

| stage | что добавляется |
|---|---|
| 1 | рама одной массой |
| 2 | лонжероны, рессоры над осями |
| 3 | поперечины, задний брус с красными фонарями |
| 4 | брызговики (резина) за тандемом |
| 5 | полоса катафотов на брусе, тёмный металл |
