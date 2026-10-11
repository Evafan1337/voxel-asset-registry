---
id: td_leg
title: TD механическая нога
type: part
category: td_limb
inherits: null
generator_version: 2
complexity_level: 1
tags: [tower_defence, enemy, blockout]
interface:
  grid_size: [3, 4, 2]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [leg]                # +Z сокета — от бедра к стопе, +X — наружу (сгиб колена)
  sockets: []
params:
  leg_length: {type: float, default: 0.24, min: 0.1, max: 0.8, description: "вылет от бедра до низа стопы; = lift корпуса"}
  thickness: {type: float, default: 0.05, min: 0.03, max: 0.14}
  knee_out: {type: float, default: 0.14, min: 0.0, max: 0.35, description: "вынос колена наружу"}
  foot_size: {type: float, default: 0.08, min: 0.04, max: 0.2}
  palette_color: {type: enum, default: steel, values: [steel, steel_dark, stone_dark, signal_red]}
---
Компактная механическая нога: бедренный шарнир, два сегмента с коленом наружу, опорная
стопа. Строится вдоль `+Z` (от точки крепления к стопе), поэтому одинаково работает на любом
`leg`-сокете корпуса. Отдельно в превью «стоит на бедре» — это нормально.
