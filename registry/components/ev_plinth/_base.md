---
id: ev_plinth
title: Витрины · подиум эволюции
type: structure
category: display
inherits: null
generator_version: 2
complexity_level: 1
tags: [showcase, evolution, transport]
interface:
  grid_size: [240, 2, 60]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: []
  sockets:
    - {name: top, type: roof, position: [0.0, 0.2, 0.0], description: "Центр верха; смонтированная модель развёрнута носом в +X (−Y модели → +X)"}
    - {name: center, type: ground, position: [0.0, 0.2, 0.0], description: "Центр верха без поворота"}
    - {name: left_end, type: ground, position: [-3.0, 0.2, 0.0], description: "Левый край верха: с него начинается ряд подиумов на основании"}
    - {name: next, type: ground, position: [3.0, 0.0, 0.0], description: "Правый край у пола: сюда ставится следующий подиум ряда"}
design_intent:
  role: display_plinth
  purpose: "Подиум стадии эволюции: номер стадии точками, стрелка к следующей"
  primary_parts: [plinth]
  secondary_parts: [marks]
  forbidden: [orphan_geometry]
params:
  width: {type: float, default: 6.0, min: 0.8, max: 60.0, description: "Вдоль ряда (X), м"}
  depth: {type: float, default: 3.0, min: 0.8, max: 15.0, description: "Поперёк ряда (Y), м"}
  height: {type: float, default: 0.2, min: 0.05, max: 0.4}
  pips: {type: int, default: 0, min: 0, max: 5, description: "Точек стадии на передней кромке (1–5)"}
  arrow: {type: bool, default: false, description: "Стрелка на полу справа — к следующей стадии"}
  gap: {type: float, default: 1.2, min: 0.6, max: 4.0, description: "Зазор до следующего подиума: длина стрелки"}
  edge: {type: bool, default: true, description: "Яркая передняя кромка"}
  color: {type: enum, default: steel_dark, values: [steel_dark, stone_dark, stone, plaster, soot, steel]}
  accent: {type: enum, default: paint_yellow, values: [paint_yellow, signal_orange, signal_blue, plaster, signal_red]}
---
Подиум для витрин «Эволюция модели» (семейство `transport`, но годится для чего угодно).
Низкая плита по центру; `pips` точек на передней кромке — номер стадии (1–5), стрелка-шеврон на
полу справа ведёт к следующему подиуму.

Сокеты на центре верха:
- `top` — повёрнут на 90°: модель, смотрящая в −Y (как весь транспорт `vh_`), встаёт носом в
  +X — по направлению ряда. В изометрии видно 3/4 спереди, во фронтальном виде — профиль;
- `center` — без поворота;
- `left_end` (левый край верха) и `next` (правый край у пола) — ряд собирается цепочкой: первый
  подиум на `left_end` основания, каждый следующий на `next` предыдущего. Так смещения слотов
  остаются в пределах ±10 м при ряде любой длины.
