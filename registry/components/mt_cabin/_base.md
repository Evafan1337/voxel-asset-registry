---
id: mt_cabin
title: Модульный грузовик · кабина
type: part
category: truck_kit
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular]
interface:
  grid_size: [12, 10, 12]
  voxel_size: 0.25
  pivot: ground
  mounts: []
  sockets: []
design_intent:
  role: cab
  purpose: "Кабина с капотом: стёкла, решётка, фары, подкрылки, зеркала, подножки"
  primary_parts: [cab]
  secondary_parts: []
  relationships: []
  forbidden: [orphan_geometry]
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME (материалы)"}
  paint: {type: enum, default: paint_royal, description: "Окраска кабины", values: [paint_royal, signal_red, paint_yellow, paint_green, olive, plaster, signal_orange]}
---
Кабина набора `mt_` с капотом и бампером. Точка крепления — дорога под передней гранью кабины
(сокет `cab` шасси).

| stage | что добавляется |
|---|---|
| 1 | две массы: кабина и капот |
| 2 | ванна + клин с наклонным лобовым, капот-клин, бампер, зеркала на кронштейнах |
| 3 | тонированное стекло (лобовое на две створки, боковые), двери, решётка, жёлтые фары, подкрылки |
| 4 | рамы стёкол, планки решётки, маркеры на крыше и бортах, подножки, ручки, верхние кронштейны |
| 5 | хромовые бампер и обрамление решётки, номер, поворотники, расширители арок |
