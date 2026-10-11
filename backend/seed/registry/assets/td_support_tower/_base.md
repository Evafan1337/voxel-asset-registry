---
id: td_support_tower
title: TD Support
inherits: td_tower
complexity_level: 1
tags: [tower_defence, tower, blockout]
slots:
  ring:
    socket: pedestal.collar
    accepts: [td_ring]
    max_grid: [5, 1, 5]
    description: "энергокольцо на мачте"
  emitter:
    socket: pedestal.top
    accepts: [td_light]
    max_grid: [4, 1, 2]
---
BUFF / ENERGY / UTILITY: без ствола — тонкая мачта, крупное кольцо и излучатель на вершине.
Пьедестал здесь — вариант-мачта того же `td_pedestal`.
