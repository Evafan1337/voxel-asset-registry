---
id: mt_toolbox
title: Модульный грузовик · инструментальный ящик
type: part
category: truck_kit
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular]
interface:
  grid_size: [3, 3, 3]
  voxel_size: 0.25
  pivot: ground
  mounts: []
  sockets: []
design_intent:
  role: tool_box
  purpose: "Инструментальный ящик на левом лонжероне перед тандемом"
  primary_parts: [toolbox]
  secondary_parts: []
  relationships: []
  forbidden: [orphan_geometry]
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME (материалы)"}
---
Инструментальный ящик набора `mt_` на левом борту перед задними осями. Точка крепления —
дорога под ящиком (сокет `toolbox` шасси).

| stage | что добавляется |
|---|---|
| 1 | блок |
| 2 | крышка |
| 3 | контур дверцы, кронштейн к лонжерону |
| 4 | ручка, защёлки |
| 5 | тёмный металл, петли |
