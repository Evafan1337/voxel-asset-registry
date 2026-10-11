---
id: mt_tank
title: Модульный грузовик · топливный бак
type: part
category: truck_kit
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular]
interface:
  grid_size: [3, 3, 4]
  voxel_size: 0.25
  pivot: ground
  mounts: []
  sockets: []
design_intent:
  role: fuel_tank
  purpose: "Топливный бак на левом лонжероне"
  primary_parts: [tank]
  secondary_parts: []
  relationships: []
  forbidden: [orphan_geometry]
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME (материалы)"}
---
Топливный бак набора `mt_` на левом борту под передней частью фургона. Точка крепления —
дорога под баком (сокет `tank` шасси).

| stage | что добавляется |
|---|---|
| 1–2 | блок |
| 3 | цилиндр на кронштейнах к лонжерону |
| 4 | хомуты |
| 5 | полированная сталь, крышка горловины |
