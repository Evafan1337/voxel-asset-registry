---
id: td_panel
title: TD панель
type: structure
category: td_structure
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, environment, blockout]
interface:
  grid_size: [8, 3, 3]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [roof, ground, surface]
  sockets:                     # номинально для 1.0×0.38×0.14
    - {name: top, type: roof, position: [0.0, 0.38, 0.0], description: "верхняя кромка — световая полоса"}
    - {name: side_left, type: roof, position: [-0.5, 0.0, 0.0], description: "низ левого торца — опора"}
    - {name: side_right, type: roof, position: [0.5, 0.0, 0.0]}
params:
  width: {type: float, default: 1.0, min: 0.1, max: 2.0, description: "вдоль X"}
  height: {type: float, default: 0.38, min: 0.04, max: 0.7, description: "вдоль +Z сокета (вверх или вылет наружу)"}
  panel_thickness: {type: float, default: 0.14, min: 0.03, max: 0.5, description: "вдоль Y"}
  chamfer: {type: float, default: 0.03, min: 0.0, max: 0.1}
  frame: {type: bool, default: true, description: "тёмный цоколь"}
  accent: {type: bool, default: false, description: "оранжевая полоса по лицу"}
  palette_color: {type: enum, default: steel, values: [steel, steel_dark, stone, stone_dark, signal_blue, signal_red]}
---
Бронепанель общего назначения: стенка укрытия, наплечник корпуса, стабилизатор дрона.
Растёт по `+Z` сокета: на земле это стенка вверх, на `surface`-сокете — пластина, торчащая
наружу (`height` = вылет). Сокеты `side_left/right` у нижних торцов — сюда встают опоры.
