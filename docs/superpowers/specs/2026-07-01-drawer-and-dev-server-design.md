# Drawer UI and Dev Server Lifecycle Design

## Goal

Fix the orphaned Vite dev-server process when the pywebview app exits, and refactor the frontend into a left-drawer application shell with task and settings views.

## Current Evidence

- `run.sh` starts `npm run dev &` without storing the process ID or registering a cleanup trap.
- Existing orphaned processes were observed with PPID `1`.
- `frontend/src/App.jsx` currently renders a single-page form with inline styles and no settings editor.

## Design

`run.sh` will own the frontend dev-server lifecycle. It will start Vite in the background, store its PID, register a cleanup trap for `EXIT`, `INT`, and `TERM`, and kill the dev-server process group when the desktop app exits. This keeps development mode simple while preventing port 5173 from being left occupied.

The React app will become a two-view shell. A fixed left drawer contains `任务` and `设置`. The task view contains the existing video/source/output/style inputs, run button, error state, and progress state. The settings view exposes the current backend settings for Whisper, LLM, and Minimax through the existing `get_settings` and `update_settings` pywebview API.

The implementation will stay dependency-light: no router, UI framework, or state management library. Styling will move from inline JSX into `frontend/src/index.css`.

## Error Handling

- The task view keeps the existing validation that both videos are required.
- Workflow start failures reset the running state and show the error.
- Settings saves show a short status message.
- Missing nested settings values fall back to empty strings so the settings page does not crash before settings are loaded.

## Verification

- Add a small test that documents the expected cleanup mechanics in `run.sh`.
- Run `bash -n run.sh`.
- Run `.venv/bin/python -m unittest discover -s tests`.
- Run `cd frontend && npm run build`.
