---
id: evo_heli_light
title: Эволюция модели · лёгкий вертолёт
type: structure
inherits: null
generator_version: 1
complexity_level: 3
tags: [transport, evolution, showcase, animated]
poly_limit: 40000        # a showcase of 17 vehicle models
interface:
  grid_size: [222, 17, 60]
  voxel_size: 0.25
  pivot: bottom_center
  sockets: []
params: {}
slots:
  floor: {socket: null, accepts: [display], max_grid: [240, 40, 60]}
  p_s1: {socket: floor.left_end, accepts: [display], max_grid: [240, 40, 60], required: false}
  v_s1: {socket: p_s1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  p_s2: {socket: p_s1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  v_s2: {socket: p_s2.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  p_s3: {socket: p_s2.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  v_s3: {socket: p_s3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  p_s4: {socket: p_s3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  v_s4: {socket: p_s4.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  p_s5: {socket: p_s4.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  v_s5: {socket: p_s5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_cabin_1: {socket: floor.left_end, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_cabin_1: {socket: kp_cabin_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_cabin_3: {socket: kp_cabin_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_cabin_3: {socket: kp_cabin_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_cabin_5: {socket: kp_cabin_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_cabin_5: {socket: kp_cabin_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_rotor_1: {socket: kp_cabin_5.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_rotor_1: {socket: kp_rotor_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_rotor_3: {socket: kp_rotor_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_rotor_3: {socket: kp_rotor_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_rotor_5: {socket: kp_rotor_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_rotor_5: {socket: kp_rotor_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_tail_rotor_1: {socket: kp_rotor_5.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_tail_rotor_1: {socket: kp_tail_rotor_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_tail_rotor_3: {socket: kp_tail_rotor_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_tail_rotor_3: {socket: kp_tail_rotor_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_tail_rotor_5: {socket: kp_tail_rotor_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_tail_rotor_5: {socket: kp_tail_rotor_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_skids_1: {socket: kp_tail_rotor_5.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_skids_1: {socket: kp_skids_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_skids_3: {socket: kp_skids_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_skids_3: {socket: kp_skids_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_skids_5: {socket: kp_skids_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_skids_5: {socket: kp_skids_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
---
Витрина «Эволюция модели» для `vh_heli_light`: одна и та же модель шаг за шагом.

- **Задний ряд** — стадии 1…5 (блокаут → базовая геометрия → развитие формы → детализация →
  игровая) на подиумах; точки на кромке — номер стадии, стрелки ведут к следующей.
  Модели стоят носом вправо (+X): в изометрии 3/4 спереди, во фронтальном виде — профиль.
- **Передний ряд** — ключевые блоки на стадиях 1, 3, 5 (оранжевые стрелки): `cabin`, `rotor`, `tail_rotor`, `skids`.

Раскладку считает скрипт по габаритам собранных вариантов; модели — наследники одной цепочки
`vh_heli_light` v001 → v005, ключевые блоки — v006…v017.
