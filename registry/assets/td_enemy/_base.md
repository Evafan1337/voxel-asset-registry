---
id: td_enemy
title: TD враг (база семейства)
abstract: true
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, enemy, blockout]
interface:
  grid_size: [6, 6, 6]
  voxel_size: 0.25
  pivot: ground                # точка отсчёта — на пути под врагом (дрон парит над ней)
  sockets: []
params: {}
slots:
  hull:
    socket: null
    accepts: [td_body]
    max_grid: [4, 7, 4]
  sensor:
    socket: sensor
    accepts: [td_sensor]
    max_grid: [2, 2, 2]
    description: "увеличенный глаз — главный признак врага"
---
Враг Tower Defence: корпус `td_body` (поднят на `lift`) и крупный красный сенсор спереди.
Смотрит вперёд (+Z glTF), по направлению движения.
