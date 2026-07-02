# Drawer UI and Dev Server Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent orphaned Vite dev-server processes and refactor the frontend into a left-drawer shell with task and settings views.

**Architecture:** `run.sh` owns the Vite child process and cleans it up on app exit. `frontend/src/App.jsx` owns view state for the drawer and uses the existing pywebview API. `frontend/src/index.css` contains layout and component styling.

**Tech Stack:** Bash, Python `unittest`, React, Vite, pywebview.

---

### Task 1: Dev Server Cleanup

**Files:**
- Modify: `run.sh`
- Create: `tests/test_run_script.py`

- [ ] Write a failing Python unittest that asserts `run.sh` records `FRONTEND_PID`, defines `cleanup`, registers `trap cleanup EXIT INT TERM`, and kills the frontend process.
- [ ] Run `.venv/bin/python -m unittest tests.test_run_script -v` and confirm it fails against the current script.
- [ ] Update `run.sh` to start Vite in the background, store the PID, and clean it on exit.
- [ ] Run `.venv/bin/python -m unittest tests.test_run_script -v` and `bash -n run.sh`.

### Task 2: Drawer Shell UI

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/index.css`

- [ ] Replace the single form page with an app shell containing a left drawer and main content area.
- [ ] Add `任务` and `设置` navigation items.
- [ ] Move existing workflow controls into the task view.
- [ ] Add settings fields for Whisper, LLM, and Minimax using `get_settings` and `update_settings`.
- [ ] Keep the frontend API mock aligned with the backend settings shape.
- [ ] Run `cd frontend && npm run build`.

### Task 3: Final Verification

**Files:**
- Read: `run.sh`
- Read: `frontend/src/App.jsx`
- Read: `frontend/src/index.css`

- [ ] Run `.venv/bin/python -m unittest discover -s tests`.
- [ ] Run `bash -n run.sh`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Inspect process list and report any existing pre-change orphaned Vite processes separately from the new fix.
