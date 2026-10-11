---
id: zk_lamp
title: Zuk · прямоугольный фонарь
type: part
category: vehicle_lamp
inherits: null
generator_version: 1
complexity_level: 2
tags: [vehicle, zuk, modular, lamp, stage3]
interface:
  grid_size: [2, 1, 2]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [vehicle_lamp, surface]
  sockets: []
design_intent:
  role: vehicle_lamp
  purpose: Прямоугольная фара или задний фонарь с отдельным светящимся рассеивателем.
  primary_parts: [housing]
  secondary_parts: [lens]
  relationships:
    - {type: attached_to, part: lens, target: housing, min_level: 2}
    - {type: symmetric, part: housing, axis: x}
  forbidden: [floating_parts, orphan_geometry]
params:
  stage: {type: int, default: 3, min: 1, max: 3, description: "1 блок; 2 серый рассеиватель; 3 корпус с утопленной светящейся линзой"}
  kind: {type: enum, default: head, values: [head, tail, marker]}
  width: {type: float, default: 0.25, min: 0.125, max: 0.5}
  height: {type: float, default: 0.1875, min: 0.125, max: 0.375}
  depth: {type: float, default: 0.0625, min: 0.0625, max: 0.125}
  body_color: {type: enum, default: metal_dark, values: [metal_dark, metal_steel, paint_gray]}
---
Переиспользуемый узел передней фары, заднего фонаря и бокового маркера.
Локальная ось Blender +Z направлена наружу; Z=0 — монтажная плоскость.
Поворот задаёт сокет `vehicle_lamp`, поэтому один генератор подходит для передней,
задней и боковой граней. Габарит, центр монтажной грани и направление сохраняются
на всех трёх стадиях. Stage 1 используют с level 0–1; готовые варианты относятся
к стадиям 2–3 и level 2.

Stage 2 сохраняет серый лист детализации. Stage 3 применяет существующие классы
`metal` и `light`: корпус и рассеиватель экспортируются отдельными mesh-узлами,
а жёлтая/красная/янтарная эмиссия остаётся цветной в GLB. Это геометрический фонарь
и материал рассеивателя; игровые световые лучи задаёт принимающий проект Godot.
Без сеток, болтов и декоративного крепежа. Линза лежит на задней пластине внутри
рамки, её передняя грань утоплена относительно корпуса.
