---
id: evo_truck
title: Эволюция модели · грузовик
type: structure
inherits: null
generator_version: 1
complexity_level: 3
tags: [transport, evolution, showcase, animated]
poly_limit: 40000        # a showcase of 17 vehicle models
interface:
  grid_size: [185, 17, 40]
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
  kp_cab_1: {socket: floor.left_end, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_cab_1: {socket: kp_cab_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_cab_3: {socket: kp_cab_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_cab_3: {socket: kp_cab_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_cab_5: {socket: kp_cab_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_cab_5: {socket: kp_cab_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_body_1: {socket: kp_cab_5.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_body_1: {socket: kp_body_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_body_3: {socket: kp_body_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_body_3: {socket: kp_body_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_body_5: {socket: kp_body_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_body_5: {socket: kp_body_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_wheel_1: {socket: kp_body_5.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_wheel_1: {socket: kp_wheel_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_wheel_3: {socket: kp_wheel_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_wheel_3: {socket: kp_wheel_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_wheel_5: {socket: kp_wheel_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_wheel_5: {socket: kp_wheel_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_chassis_1: {socket: kp_wheel_5.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_chassis_1: {socket: kp_chassis_1.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_chassis_3: {socket: kp_chassis_1.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_chassis_3: {socket: kp_chassis_3.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
  kp_chassis_5: {socket: kp_chassis_3.next, accepts: [display], max_grid: [240, 40, 60], required: false}
  k_chassis_5: {socket: kp_chassis_5.top, accepts: [vehicle], max_grid: [240, 40, 60], required: false}
---
Витрина «Эволюция модели» для `vh_truck`: одна и та же модель шаг за шагом.

- **Задний ряд** — стадии 1…5 (блокаут → базовая геометрия → развитие формы → детализация →
  игровая) на подиумах; точки на кромке — номер стадии, стрелки ведут к следующей.
  Модели стоят носом вправо (+X): в изометрии 3/4 спереди, во фронтальном виде — профиль.
- **Передний ряд** — ключевые блоки на стадиях 1, 3, 5 (оранжевые стрелки): `cab`, `body`, `wheel`, `chassis`.

Раскладку считает скрипт по габаритам собранных вариантов; модели — наследники одной цепочки
`vh_truck` v001 → v005, ключевые блоки — v006…v017.
