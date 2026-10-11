---
id: td_walker
title: TD шагающий враг (база)
abstract: true
inherits: td_enemy
tags: [tower_defence, enemy, blockout]
slots:
  leg_fl: {socket: leg_fl, accepts: [td_leg], max_grid: [3, 4, 2]}
  leg_fr: {socket: leg_fr, accepts: [td_leg], max_grid: [3, 4, 2]}
  leg_bl: {socket: leg_bl, accepts: [td_leg], max_grid: [3, 4, 2]}
  leg_br: {socket: leg_br, accepts: [td_leg], max_grid: [3, 4, 2]}
  armor_left: {socket: side_left, accepts: [td_panel], max_grid: [8, 3, 3], required: false}
  armor_right: {socket: side_right, accepts: [td_panel], max_grid: [8, 3, 3], required: false}
---
Четвероногая схема: ноги на `leg_*` сокетах корпуса, опционально бронепластины по бокам.
Правило: `leg_length` ног = `lift` корпуса — тогда стопы стоят на земле.
