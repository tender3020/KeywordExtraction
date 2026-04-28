---
name: keyword-extraction-system
description: Develop, optimize, and troubleshoot the KeywordExtraction Streamlit system end-to-end, including auth/permissions, Excel import, data management, analytics pages, UI consistency, and SQLite safety. Use when the user asks to add features, fix bugs, improve layout, refactor modules, or stabilize production behavior in this repository.
---

# KeywordExtraction System Skill

## Purpose

Use this skill to implement or fix features in this repository with consistent architecture, safe database changes, and production-friendly Streamlit UI behavior.

## Project Map

- `app.py`: app entry, auth gate, navigation routing, top shell.
- `modules/auth/pages.py`: login/register UI and user permission admin page.
- `modules/auth/service.py`: auth domain logic (password, users, permissions, verification code, admin init).
- `modules/auth/repository.py`: auth DB connection, table init, legacy migration.
- `modules/auth/settings.py`: auth env settings and DB path config.
- `modules/pages.py`: import page, data management page, analytics page.
- `modules/data_repository.py`: business DB access and CRUD/import helpers.
- `modules/ui_components.py`: global styles and reusable page widgets.
- `.streamlit/config.toml`: Streamlit client toolbar behavior.

## Data Boundaries (Must Preserve)

- Business DB: `bi_dashboard.db` (records and analytics source).
- Auth DB: `auth.db` (users and verification_codes).
- Never move auth writes back into business DB.
- Any new auth feature must go through `modules/auth/*`.

## Feature Areas

### 1) Auth and Permission
- Login by username/email/phone.
- Register by email or phone with verification code.
- Admin bootstrap and permission maintenance.
- Session refresh and forced relogin when account state changes.

### 2) Data Import
- Upload Excel, choose sheet, normalize headers.
- Optional invalid workorder filtering.
- Import feedback must reflect `(inserted_count, total_count)`.

### 3) Data Management
- Filter/search rows, control display count.
- Add/edit/delete records with robust error handling.

### 4) Analytics
- Distribution pie, issue analysis, trend analysis.
- Keep label terminology consistent (use `是否客责`).
- Preserve date parsing and empty-state handling.

### 5) UI and Streamlit Shell
- Keep style consistency via `modules/ui_components.py`.
- Avoid brittle DOM hacks for core logic.
- If hiding toolbar elements, scope CSS narrowly and verify no collateral effects.

## Standard Execution Workflow

1. Read context from `app.py` and target module(s).
2. Identify minimal safe change set.
3. Implement with existing naming and component patterns.
4. Validate:
   - Run lints on touched files.
   - Run `python -m compileall` on touched modules.
5. Regress key flows:
   - login/logout
   - permission-based menu visibility
   - import and CRUD
   - analytics filters and charts
6. Report:
   - changed files
   - behavior impact
   - verification results

## Guardrails

- Do not break current route and permission checks in `app.py`.
- Do not change DB schema semantics without migration-safe handling.
- Do not use broad CSS selectors that hide unrelated content.
- Do not introduce unpinned dependencies without explicit user request.
- Do not use destructive git commands.

## Common Fix Recipes

### A) Admin init crashes with unique constraint
- Check `ensure_default_admin()` in `modules/auth/service.py`.
- Prefer promote-existing-user logic before inserting new admin.
- Avoid fixed unique values that can collide (for example fixed email).

### B) Import success text mismatches actual behavior
- Verify `import_to_db()` return shape.
- Ensure page message uses returned inserted count, not guessed count.

### C) Permission page missing in menu
- Verify user has `PERMISSION_ADMIN`.
- Verify route mapping in `app.py` includes user admin page.
- Verify refreshed session user still active.

### D) Login page layout regression
- Constrain style changes to auth page CSS.
- Re-verify centered card, mode toggle, and form readability.

## Output Format for Task Completion

When finishing work with this skill, return:

1. What changed (by file path).
2. Why it changed (brief rationale).
3. Verification performed (lint/compile/manual flow checks).
4. Any follow-up risk or optional improvements.

