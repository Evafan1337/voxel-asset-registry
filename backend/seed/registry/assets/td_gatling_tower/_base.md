---
id: td_gatling_tower
title: TD Gatling
inherits: td_tower
complexity_level: 1
tags: [tower_defence, tower, blockout]
slots:
  head:
    socket: pedestal.top
    accepts: [td_body]
    max_grid: [4, 7, 4]
  weapon:
    socket: head.weapon
    accepts: [td_barrel]
    max_grid: [3, 4, 3]
    description: "длинная связка стволов вперёд"
  head_light:
    socket: head.top
    accepts: [td_light]
    max_grid: [4, 1, 2]
    required: false
---
FAST / DIRECT FIRE / SINGLE TARGET: компактный корпус на пьедестале и длинная связка
стволов вперёд — силуэт «пушки».
