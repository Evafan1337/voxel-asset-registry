---
id: td_base
title: TD основание
type: structure
category: td_structure
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, blockout]
interface:
  grid_size: [8, 2, 8]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [ground, roof]
  sockets:                     # номинально для width=4, height=0.22 (glTF-оси)
    - {name: support, type: roof, position: [0.0, 0.22, 0.0], description: "центр верхней плиты — опора башни"}
    - {name: front, type: surface, position: [0.0, 0.11, 0.5], description: "центр передней грани, +Z наружу — маркер/огонь"}
    - {name: side_left, type: surface, position: [-0.5, 0.11, 0.0]}
    - {name: side_right, type: surface, position: [0.5, 0.11, 0.0]}
params:
  width: {type: int, default: 4, min: 2, max: 8, description: "сторона квадрата, воксели (4 = 1 тайл = 1 м)"}
  height: {type: float, default: 0.22, min: 0.08, max: 0.4, description: "высота основания, м"}
  chamfer: {type: float, default: 0.1, min: 0.0, max: 0.3, description: "срез вертикальных рёбер (0.25+ → почти восьмигранник)"}
  tiers: {type: int, default: 2, min: 1, max: 2, description: "2 — тёмный цоколь и светлая верхняя плита"}
  rim: {type: enum, default: none, values: [none, full, straight], description: "бортик тайла дороги: по периметру / только по бокам X (прямой участок)"}
  accent: {type: bool, default: true, description: "оранжевые полосы на боковых гранях"}
  palette_color: {type: enum, default: steel, values: [steel, steel_dark, stone, stone_dark]}
---
Общее основание семейства `tower_defence`: квадратная плита с фаской (восьмиугольный
силуэт при большом `chamfer`), тёмный цоколь и светлая верхняя плита, оранжевые полосы —
«подпись» линейки. Одна сущность служит и основанием башен, и тайлом дороги (`rim`).

Сокеты: `support` (roof) — на него ставится пьедестал; `front`, `side_left`, `side_right`
(surface, +Z наружу из грани) — маркеры/огни.
