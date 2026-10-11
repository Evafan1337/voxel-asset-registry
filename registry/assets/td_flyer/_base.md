---
id: td_flyer
title: TD Flyer
inherits: td_enemy
complexity_level: 1
tags: [tower_defence, enemy, blockout]
slots:
  fin_left: {socket: side_left, accepts: [td_panel], max_grid: [8, 3, 3]}
  fin_right: {socket: side_right, accepts: [td_panel], max_grid: [8, 3, 3]}
  spike:
    socket: bottom
    accepts: [td_barrel]
    max_grid: [3, 4, 3]
    required: false
---
Летающий дрон: гранёный круглый корпус висит на высоте `lift`, крупный круглый глаз,
стабилизаторы по бокам (та же `td_panel`) и шип снизу (тот же `td_barrel`). Ног нет.
