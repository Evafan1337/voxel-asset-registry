---
id: td_missile_tower
title: TD Missile
inherits: td_tower
complexity_level: 1
tags: [tower_defence, tower, blockout]
slots:
  head:
    socket: pedestal.top
    accepts: [td_body]
    max_grid: [4, 7, 4]
    description: "короткая шея под ракетницу"
  launcher:
    socket: head.top
    accepts: [td_launcher]
    max_grid: [4, 3, 4]
---
HEAVY / AREA DAMAGE: массивный блок ракетницы с крупными пусковыми трубами — самая тяжёлая
верхняя масса в линейке.
