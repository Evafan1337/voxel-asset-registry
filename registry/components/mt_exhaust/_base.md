---
id: mt_exhaust
title: Модульный грузовик · выхлоп
type: part
category: truck_kit
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular]
interface:
  grid_size: [3, 10, 3]
  voxel_size: 0.25
  pivot: ground
  mounts: []
  sockets: []
design_intent:
  role: exhaust
  purpose: "Вертикальная выхлопная труба за кабиной"
  primary_parts: [exhaust]
  secondary_parts: []
  relationships: []
  forbidden: [orphan_geometry]
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME (материалы)"}
---
Выхлопная труба набора `mt_` за кабиной на левом борту. Точка крепления — дорога под трубой
(сокет `exhaust` шасси).

| stage | что добавляется |
|---|---|
| 1 | колонна одной массой |
| 2 | труба с загнутым назад верхом, кронштейн к кабине, приёмная труба в раму |
| 3 | теплозащитный кожух |
| 4 | хомуты |
| 5 | хром и перфорация кожуха |
