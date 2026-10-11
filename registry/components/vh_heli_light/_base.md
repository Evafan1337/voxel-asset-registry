---
id: vh_heli_light
title: Транспорт · лёгкий вертолёт (эволюция)
type: part
category: vehicle
inherits: null
generator_version: 8
complexity_level: 3
tags: [transport, evolution, animated]
poly_limit: 5000
interface:
  grid_size: [22, 12, 30]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: []
  sockets: []
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING (крупные массы) · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME"}
  part: {type: enum, default: all, values: [all, cabin, rotor, tail_rotor, skids], description: "all — вертолёт целиком; иначе ключевой блок: кабина, главный ротор, хвостовой ротор, лыжи"}
  color: {type: enum, default: signal_red, description: "Корпус", values: [signal_red, paint_blue, paint_yellow, olive, plaster, signal_orange, paint_green]}
  trim: {type: enum, default: steel_dark, description: "Рама кабины, капот, стойки", values: [steel_dark, steel, soot, olive_dark]}
  tip: {type: enum, default: signal_orange, description: "Законцовки лопастей (стадии 4–5)", values: [signal_orange, paint_yellow, plaster, signal_red]}
  rotor_turns: {type: int, default: 2, min: 1, max: 4, description: "Оборотов несущего винта за цикл work; рулевой — втрое больше"}
---
Лёгкий вертолёт семейства `transport` — «эволюция модели» по правилам блокаута
(`builder/blockout.py`, раздел «Blockout and refinement rules» в CLAUDE.md). Нос в −Y, стоит
лыжами на z = 0. Генератор — чистый план из масс, граней, регионов и портов; `vehlib.render`
рисует его в Blender, тесты читают план без Blender.

Скелет (MACRO_GRID 0,25 м, общий для всех стадий):
- `cabin` — клин 1,5 × 2 × 1,5 м; `rotor_mount` — центр его крыши, мачта 0,5 м до `rotor_hub`;
- `tail_mount` — на задней грани кабины (z 1,5): оттуда начинается балка до `tail_end` (y 3,5);
- `tail_rotor_mount` — у киля; `skid_front/rear_left/right` — порты на днище для стоек лыж.

| stage | что добавляется |
|---|---|
| 1 · MASSING | 5 масс: кабина, балка с килём, мачта с винтом, полозья, ось рулевого винта |
| 2 · SILHOUETTE | кабина → ванна + фонарь (стекло), горб двигателя, тонкий киль, стабилизатор, трубы лыж, стойки |
| 3 · STRUCTURE | фонарь-каркас с регионами стекла (лобовое на 2 створки, боковые), двери, решётчатая балка по рёбрам массы, редуктор, основание мачты, носки лыж |
| 4 · DETAIL | рамы по границам стёкол, воздухозаборники, антенна, хвостовая опора, автомат перекоса, подножки, 4 лопасти рулевого |
| 5 · GAME | маяк, фара, навигационные огни, полоса, выхлоп, башмаки лыж, цветные законцовки |

Винты крутятся на уровне 3 при любой стадии: анимация не определяет детализацию.
v001 → v005 — цепочка стадий; ключевые блоки (`part`: cabin, rotor, tail_rotor, skids) —
наследники стадий 1, 3 и 5.
