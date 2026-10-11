---
id: td_pedestal
title: TD пьедестал / мачта
type: structure
category: td_structure
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, blockout]
interface:
  grid_size: [3, 7, 3]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [roof, ground]
  sockets:
    - {name: top, type: roof, position: [0.0, 0.42, 0.0], description: "верх — голова башни, излучатель"}
    - {name: collar, type: roof, position: [0.0, 0.31, 0.0], description: "на оси на высоте collar_at·height — кольцо вокруг мачты"}
params:
  width: {type: float, default: 0.34, min: 0.1, max: 0.6, description: "ширина ствола у основания, м"}
  height: {type: float, default: 0.42, min: 0.15, max: 1.5}
  taper: {type: float, default: 0.15, min: 0.0, max: 0.6, description: "сужение к верху"}
  shape: {type: enum, default: octagon, values: [square, octagon]}
  foot: {type: bool, default: true, description: "широкая «юбка» у основания"}
  collar_at: {type: float, default: 0.75, min: 0.3, max: 0.95, description: "высота сокета collar, доля от height"}
  accent: {type: bool, default: false, description: "оранжевый пояс у верха (опоры укрытий)"}
  palette_color: {type: enum, default: steel, values: [steel, steel_dark, stone, stone_dark]}
---
Вертикальная опора: поворотное крепление башни, мачта support-башни или стойка укрытия —
это один генератор с разными параметрами. «Юбка» внизу, сужающийся ствол, тёмная крышка.
Сокет `top` — для головы/излучателя, `collar` — на оси ствола, кольцо надевается на мачту.
