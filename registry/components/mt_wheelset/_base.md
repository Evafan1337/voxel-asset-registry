---
id: mt_wheelset
title: Модульный грузовик · колёсная ось
type: part
category: truck_kit
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular]
interface:
  grid_size: [10, 5, 5]
  voxel_size: 0.25
  pivot: ground
  mounts: []
  sockets: []
design_intent:
  role: wheel_set
  purpose: "Ось с двумя колёсами или спаренными колёсами сзади"
  primary_parts: [wheels]
  secondary_parts: []
  relationships:
    - {type: touches_ground, part: wheels}
  forbidden: [orphan_geometry]
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME (материалы)"}
  dual: {type: bool, default: false, description: "Спаренные колёса (задние оси)"}
---
Колёсная ось набора `mt_`: ось на высоте радиуса колеса, шины (резина), обод, колпак, гайки.
Точка крепления — дорога под центром оси (сокеты `axle_*` шасси). `dual` — спаренные колёса задних
осей и картер моста.

| stage | что добавляется |
|---|---|
| 1 | восьмигранные шины на плоской грани, ось |
| 2 | квадратная ступица референса |
| 3 | шина 12 граней, обод, колпак, картер моста |
| 4 | гайки |
| 5 | шина 16 граней, стальной обод, хромовый колпак |
