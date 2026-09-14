# deblaot-gui

A PyQt5 desktop front end for [deblaot](../deblaot) -- the backend that does the actual work of applying MacDebloat's tweaks. This app is a thin client: every button here just calls deblaot's REST API and shows you what came back.

![deblaot GUI](Assets/screenshot.png)

## Requirements

- macOS
- Python 3.10+
- The `deblaot` backend cloned as a **sibling folder** to this one:
  ```
  <repo>/deblaot/
  <repo>/deblaot-gui/   <- this app
  ```

## Running it

```bash
cd deblaot-gui
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python3 main.py
```

On launch, the app checks whether deblaot is already running on `127.0.0.1:8765`; if not, it starts it for you (using deblaot's own virtualenv if `deblaot/.venv` exists, so you don't need FastAPI/uvicorn installed here too). Closing the window shuts the backend back down again, but only if this app was the one that started it -- if you had it running yourself in a terminal, it's left alone.

If auto-start can't find or launch the backend, you'll get a clear error dialog telling you to run `deblaot/run.sh` manually first.

## What's in the window

- **Sidebar**: the 8 tweak categories, each with a count, plus "Run Recommended Preset" and "Run Everything" at the bottom.
- **Main panel**: every tweak in the selected category as a card -- title, description, an `ADMIN` or `EXPERIMENTAL` badge where relevant, and an Apply button (or a dropdown + Apply, for tweaks like Dock position that need a choice).
- **Activity log**: a running console at the bottom of every action's result, success or failure, in addition to the per-card result text.
- **History & Revert**: opens a dialog listing recent runs, each with its own Revert button.

Experimental tweaks and bundled-app removal ask for confirmation before doing anything, same as the CLI and the API do.

## Why a GUI on top of an API instead of one monolithic app

Keeping the actual tweak logic entirely in deblaot means this window is disposable -- it's ~800 lines of "call an endpoint, show the result," with no macOS-specific logic duplicated here. A menu-bar app, a web dashboard, or a completely different GUI toolkit could all sit on the same backend without touching this code at all.

The one thing worth calling out: applying a tweak can pop a native macOS admin-password dialog on the backend side, which can take real human time to click through. Every API call in this app runs on a background `QThread` (see `deblaot_gui/workers.py`) specifically so that wait never freezes the window.

## Project layout

```
deblaot-gui/
  deblaot_gui/
    main_window.py       # the whole window: layout, category/tweak rendering, apply flow
    history_dialog.py    # the History & Revert dialog
    api_client.py         # thin wrapper over deblaot's REST API
    backend_launcher.py   # finds or starts the deblaot process
    workers.py             # QThread wrapper so API calls never block the UI
    styles.py              # the QSS stylesheet
  main.py                  # entry point
  requirements.txt
```
