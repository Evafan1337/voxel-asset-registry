---
id: td_path_tile
title: TD тайл пути
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, environment, blockout]
interface:
  grid_size: [4, 2, 4]
  voxel_size: 0.25
  pivot: bottom_center
  sockets: []
params: {}
slots:
  tile:
    socket: null
    accepts: [td_base]
    max_grid: [8, 2, 8]
---
Квадратный тайл пути 1×1 м (4 вокселя) — вариант общего `td_base` с бортиками. Кладётся
на регулярную сетку. Прямой участок — `rim: straight`. Углы, T и крест появятся как
варианты `rim`, когда понадобятся.
