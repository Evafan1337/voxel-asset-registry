---
id: td_sensor
title: TD сенсор / глаз
type: part
category: td_sensor
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, enemy, blockout]
interface:
  grid_size: [2, 2, 2]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [surface, roof]      # растёт вдоль +Z сокета (вперёд из лица корпуса)
  sockets: []
params:
  shape: {type: enum, default: box, values: [box, round]}
  size: {type: float, default: 0.14, min: 0.08, max: 0.4}
  depth: {type: float, default: 0.06, min: 0.03, max: 0.3}
  eye: {type: float, default: 0.6, min: 0.3, max: 0.9, description: "размер глаза, доля от size"}
  eye_color: {type: enum, default: signal_red, values: [signal_red, signal_blue, signal_orange]}
  palette_color: {type: enum, default: steel_dark, values: [steel, steel_dark, stone_dark]}
---
Сенсорный модуль врага: корпус-рамка и крупный яркий «глаз» — главный признак врага на
игровой дистанции (увеличен намеренно). Растёт вперёд вдоль `+Z` сокета `sensor`.
