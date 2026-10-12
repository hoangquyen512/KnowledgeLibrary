# Knowledge Library Brand Identity — Design

**Date:** 2026-08-27  
**Status:** Approved (Approach 1 — SVG files + React wrappers; user chose implement immediately)

## Goal

Unify app identity around the chibi ant mascot (navy–blue–violet, Q backpack, magnifier) without changing business logic or primary layouts.

## Decisions

- **Assets:** SVG sources under `apps/web/public/brand/`; PNG/ICO/OG rasterized from those SVGs.
- **Components:** `BrandLogo`, `BrandMark`, `BrandMascot`, `AppIcon`, `BrandEmptyState`, `BrandLoading`.
- **Layers:** Brand (mascot) vs product nav (Lucide) vs AI action (brand-colored functional SVGs).
- **Palette:** `#102A6A`, `#2F5BEA`, `#4B4FE8`, `#6C3EF0`, `#D9D5FF`.
- **Name:** Knowledge Library only. Tagline: Explore • Understand • Grow.
- **Size rule:** &lt;40px → icon mark (head + magnifier); full mascot for login/empty/welcome/OG.

## Out of scope

API/auth/layout refactors; replacing Lucide nav/source icons with mascot; mascot in every toast/button.
