---
id: td_launcher
title: TD ракетная установка
type: part
category: td_weapon
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, blockout]
interface:
  grid_size: [4, 3, 4]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [roof]
  sockets:
    - {name: muzzle, type: surface, position: [0.0, 0.22, 0.29], description: "центр пусковой панели"}
params:
  width: {type: float, default: 0.58, min: 0.3, max: 0.9}
  height: {type: float, default: 0.44, min: 0.2, max: 0.7}
  depth: {type: float, default: 0.5, min: 0.2, max: 0.8}
  rows: {type: int, default: 2, min: 1, max: 3}
  cols: {type: int, default: 2, min: 1, max: 3}
  chamfer: {type: float, default: 0.06, min: 0.0, max: 0.15}
  palette_color: {type: enum, default: signal_blue, values: [signal_blue, steel, steel_dark, signal_red]}
  tube_color: {type: enum, default: soot, values: [soot, steel_dark, signal_orange]}
---
Коробчатая пусковая установка: массивный блок, спереди (−Y) сетка крупных пусковых труб
`rows × cols`. Трубы — выступающие обода с тёмной сердцевиной: читаются как отверстия.
Ставится на крышу корпуса (`top`).
