# FPU Job Scheduler

This repository now contains a fully independent, self-contained web application for job scheduling and execution tracking, plus an optional MQTT-based FMS simulator.

## What changed

- Removed the Streamlit-based runtime from the active app.
- Replaced it with a standalone static web app built with plain HTML, CSS, and JavaScript.
- The app runs entirely in the browser and keeps its state in `localStorage`.
- No third-party Python packages are required.

## Files to open

- `index.html` - the main application
- `styles.css` - the visual theme
- `app.js` - all app logic
- `serve.py` - optional local static server
- `fms_simulator.py` - optional MQTT companion service

## How to run

### Option 1: Open directly

Open `index.html` in a browser.

### Option 2: Use the built-in server

Run:

```powershell
python serve.py
```

Then open:

```text
http://127.0.0.1:8000
```

## MQTT + FMS

The browser app can publish MQTT events to a broker over WebSockets. To get live FMS-style responses, run the optional simulator in a separate terminal:

```powershell
pip install -r fms_requirements.txt
python fms_simulator.py
```

By default the browser app uses the public MQTT broker `wss://broker.hivemq.com:8884/mqtt`. You can change the broker URL and client ID from the MQTT Communication panel in the sidebar.

## Behavior

- Orders/Jobs tab for metadata, operation building, catalog, and draft preview
- Scheduling tab for queue management and a running scheduler simulation
- Execution tab for focused job control with previous, advance, and complete actions
- Catalog tab for operation reference and FPU basics
- IST-based date and timestamp handling
- Field-specific suggestions for metadata inputs
- Route flow shown as animated cards instead of a table
- MQTT communication status, publish logs, and FMS command publishing
- Optional local FMS simulator that can subscribe to the same topics and publish live status updates

## Notes

The previous Streamlit files are still in the repository as legacy reference, but they are no longer the active app.
