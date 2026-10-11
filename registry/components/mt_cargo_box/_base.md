---
id: mt_cargo_box
title: Модульный грузовик · фургон
type: part
category: truck_kit
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular]
interface:
  grid_size: [11, 10, 20]
  voxel_size: 0.25
  pivot: ground
  mounts: []
  sockets: []
design_intent:
  role: cargo_box
  purpose: "Фургон в каркасе на подрамнике"
  primary_parts: [box]
  secondary_parts: []
  relationships: []
  forbidden: [orphan_geometry]
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME (материалы)"}
  color: {type: enum, default: paint_gray, description: "Филёнки фургона", values: [paint_gray, plaster, steel, paint_royal, olive, signal_red]}
---
Фургон набора `mt_`. Точка крепления — дорога под центром фургона (сокет `box` шасси).
С третьей стадии каркас (стойки, обвязка) идёт по рёбрам массы stage 1, а филёнки утоплены на
DETAIL — ни одна деталь не лежит вровень с гранью другого цвета.

| stage | что добавляется |
|---|---|
| 1 | фургон одной массой |
| 2 | подрамник до лонжеронов |
| 3 | каркас и утопленные филёнки |
| 4 | швы филёнок, красно-белые полосы катафотов, габаритные огни, задние двери с петлями |
| 5 | хромовые угловые накладки, запоры |
