# HeatTrax v2.0 Refactoring Plan

## Overview

This refactor aims to simplify the codebase for easier editing, unify the mobile and desktop UI into a cohesive experience (simple mobile view + feature-rich desktop view), and improve maintainability — all while preserving existing application logic and behavior.

## Goals

1. **Code Simplification** — Reduce complexity, remove dead code paths, improve readability
2. **Unified UI Architecture** — Single codebase serving both mobile (simple) and desktop (full configuration) views, replacing the current fragmented approach
3. **Improved Configuration** — Streamlined config handling with clear separation of concerns
4. **UI Component Separation** — Clean separation between mobile and desktop components
5. **Preserve All Existing Behavior** — Zero regressions; the application must work exactly as it does today

## Refactoring Contract / Acceptance Criteria

- All existing tests must continue to pass
- All API endpoints must remain functional with the same request/response contracts
- All scheduling logic must produce identical results
- Device control behavior must be unchanged
- Both mobile and desktop UIs must remain functional throughout the refactor
- Configuration files must remain backward compatible

## Phases (Suggested)

- **Phase 0: Documentation Cleanup** (current) — Fix docs to establish accurate baseline
  - #129 — Fix critical contradictions
  - #131 — Mark deprecated content
  - #133 — Complete API documentation
  - #135 — Consolidate README.md
  - #137 — Archive old refactor doc (this issue)
- **Phase 1: Code Simplification** — TBD
- **Phase 2: UI Unification** — TBD
- **Phase 3: Configuration Improvements** — TBD

## Previous Refactor

For the v1.0 refactor summary, see [docs/REFACTOR_V1.md](docs/REFACTOR_V1.md).
