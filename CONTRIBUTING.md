# Contributing

## Setup

```bash
cd screen-watch
python -m pip install -e ".[dev]"
python -m pytest -q
python -m screen_watch doctor
```

Optional extras: `[windows]` (dxcam), `[hotkey]` (pynput on macOS/Linux).

## Rules

- Observation only — no mouse/keyboard injection APIs.
- Local-only — no upload/telemetry paths.
- Logs go to **stderr** so MCP stdio stays clean.
- Prefer small modules and type hints.

## Tests

Unit tests must not require a display when possible. Platform capture smoke is manual (`once` / `focus`).

## Git workflow

Repo: https://github.com/JadissEL/screen-watch

1. Work in this directory (it has its **own** `.git`, separate from Daygrid/Wolt).
2. After a coherent change set: run `python -m pytest -q`, then commit with a clear message.
3. Push `main` so CI and the public history stay current — do not batch weeks of silent local-only work.
4. Prefer small, reviewable commits over one giant dump.
