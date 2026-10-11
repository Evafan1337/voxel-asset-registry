---
id: td_cover
title: TD укрытие
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, environment, blockout]
interface:
  grid_size: [8, 4, 3]
  voxel_size: 0.25
  pivot: bottom_center
  sockets: []
params: {}
slots:
  wall:
    socket: null
    accepts: [td_panel]
    max_grid: [8, 3, 3]
  pillar_left:
    socket: side_left
    accepts: [td_pedestal]
    max_grid: [3, 7, 3]
  pillar_right:
    socket: side_right
    accepts: [td_pedestal]
    max_grid: [3, 7, 3]
  strip:
    socket: top
    accepts: [td_light]
    max_grid: [4, 1, 2]
    required: false
---
Низкая sci-fi стенка: панель и две стойки по торцам (тот же `td_pedestal`, что и у башен),
сверху — световая полоса. Ниже линии огня башен.
