---
id: WRK-WORKSPACE
title: Workspace RBAC & Share
status: active
updated: 2026-10-07
---

# WRK-WORKSPACE

## Business rules

- BR-WRK-01: Tạo workspace → creator là OWNER.
- BR-WRK-02: Tối đa 10 workspace owned / user (409 khi vượt).
- BR-WRK-03: Workspace nhận qua share không tính vào quota owned.
- BR-WRK-04: Không gỡ OWNER cuối cùng (409).
- BR-WRK-05: Theme LIGHT/DARK/SYSTEM lưu user_settings.
- BR-WRK-06: Share link hash-at-rest; redeem sau login.

## Automation

`tests/test_workspace_phase2.py`, `tests/test_permissions_unit.py`, E2E `e2e/phase2.spec.ts`
