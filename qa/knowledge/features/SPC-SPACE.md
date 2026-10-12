---
id: SPC-SPACE
title: Space management
status: active
updated: 2026-10-07
depends_on: WRK-WORKSPACE
---

# SPC-SPACE

## Business rules

- BR-SPC-01: Tạo space → owner membership.
- BR-SPC-02: VIEWER không PATCH space.
- BR-SPC-03: Isolated space share: VIEWER không GET workspace spaces list (403).
- BR-SPC-04: Star / Recent cập nhật khi mở space.

## Automation

`tests/test_space_phase3.py`, `tests/test_space_roles_unit.py`
