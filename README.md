# FPU Job Scheduler

This repository now contains a fully independent, self-contained web application for job scheduling and execution tracking.

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

## Behavior

- Orders/Jobs tab for metadata, operation building, catalog, and draft preview
- Scheduling tab for queue management and a running scheduler simulation
- Execution tab for focused job control with previous, advance, and complete actions
- Catalog tab for operation reference and FPU basics
- IST-based date and timestamp handling
- Field-specific suggestions for metadata inputs
- Route flow shown as animated cards instead of a table

## Notes

The previous Streamlit files are still in the repository as legacy reference, but they are no longer the active app.
