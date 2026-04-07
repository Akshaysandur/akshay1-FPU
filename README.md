# Fluid Production System Dashboard

Streamlit dashboard for monitoring and controlling a fluid production system with AMRs, MQTT, and fleet management integration.

## Run

1. Install dependencies:
   `pip install -r requirements.txt`
2. Start the app:
   `streamlit run app.py`

## Deploy

Recommended option: Streamlit Community Cloud

1. Create a new GitHub repository.
2. Upload this project folder contents.
3. Make sure these files are present in the repo root:
   - `app.py`
   - `requirements.txt`
   - `layout.png`
   - `dashboard/`
4. Go to `https://share.streamlit.io/`
5. Sign in with GitHub and choose your repository.
6. Set the main file path to `app.py`.
7. Click Deploy.

After deployment, Streamlit will give you a shareable public URL.

## Update After Deployment

You can make changes later at any time:

1. Edit the code locally.
2. Commit and push changes to the same GitHub repository.
3. The deployed Streamlit app will update from the new version.

## MQTT Topics

- `fluid/fps/jobs/create`
- `fluid/fps/system/start`
- `fluid/fps/system/stop`
- `fluid/fps/system/reset`
- `fluid/fps/jobs/priority`
- `fluid/fps/amr/manual`
- `fluid/fps/scheduler/reassign`
- `fluid/fps/status/system`
- `fluid/fps/status/amr`
- `fluid/fps/scheduler/queue`
- `fluid/fps/alerts/event`

The UI falls back to simulation mode when the broker is unreachable, so the layout and AMR flow remain testable during development.
