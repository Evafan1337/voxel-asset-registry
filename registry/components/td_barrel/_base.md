---
id: td_barrel
title: TD ствол
type: part
category: td_weapon
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, blockout]
interface:
  grid_size: [3, 4, 3]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [surface]            # ствол растёт вдоль +Z сокета (вперёд из лицевой грани)
  sockets:
    - {name: muzzle, type: surface, position: [0.0, 0.5, 0.0], description: "дуло: точка вылета снаряда / вспышки"}
params:
  barrel_length: {type: float, default: 0.5, min: 0.1, max: 1.0}
  barrel_radius: {type: float, default: 0.05, min: 0.02, max: 0.12}
  count: {type: int, default: 1, min: 1, max: 4, description: "стволов в связке (gatling — 3)"}
  taper: {type: float, default: 0.0, min: 0.0, max: 0.9, description: "сужение к концу; 0.9 — шип"}
  collar: {type: bool, default: true, description: "кожух у основания"}
  muzzle: {type: bool, default: true, description: "утолщение на конце"}
  palette_color: {type: enum, default: signal_blue, values: [signal_blue, steel, steel_dark, signal_red, signal_orange]}
---
Оружейный ствол (одиночный или связка) вдоль `+Z` сокета. Намеренно крупный, чтобы
читаться с изометрической камеры. С `taper: 0.9` и без кожуха это шип, у дрона он висит под
днищем. Сокет `muzzle` на конце остаётся в GLB как точка вылета снаряда.
