# AetherShield VMS
LIVE DEPLOYMENT AT https://aethershield-ui.onrender.com/



Enterprise-grade **Smart Video Management System** with live multi-camera monitoring, AI object detection (YOLOv11 + ByteTrack), timeline-linked playback, configurable detection zones, natural-language event search, incident workflow, and analytics — built for the A-1 Launchpad 2026 case study and portfolio demos.

Inspired by commercial platforms (Verkada / Eagle Eye / Milestone), delivered as a full-stack prototype you can run locally without Docker.

## Features

### Case study (required)
- Live camera feeds (MJPEG)
- Recorded playback with timeline scrubbing
- AI intrusion / motion / object detection
- Colored timeline markers with hover details
- Detection zones (rectangle / polygon / circle) with sensitivity
- Zone-scoped event triggering
- Event list with timestamps & camera details
- Dashboard: camera status, recent detections, storage, active alerts

### Beyond the brief
- Multi-camera grid (1 / 2 / 4 / 9 / 16)
- Object tracking IDs (ByteTrack)
- Event priority (critical / high / medium / low)
- Click event → seek recording (−10s replay window)
- AI natural-language search (“Show all people after 9 PM”)
- Chat-with-video (RAG over event metadata)
- Daily AI summary + PDF security report
- Incident management workflow
- Interactive camera floor-plan map
- JWT auth with Admin / Operator / Viewer roles
- Dark enterprise UI (responsive)
- Sites (HQ and Warehouse) with a dashboard site filter
- Alert policies evaluated on stored events (after-hours zone entry, loitering by track id, unknown face)
- Operator audit log (login, alert acknowledge, incident status, policy edits)
- Notification outbox (webhook or email, simulated delivery — no outbound internet calls)
- Evidence package export for an event (camera, zone, timestamp, track id, clip window = event time − 10s)
- Camera health from heartbeats (`POST /api/cameras/{id}/heartbeat`). A camera with no heartbeat for 15 minutes is offline. The dashboard shows online and offline counts. Seed data leaves one camera offline and the rest online.
- Shifts (site, operator, start, end) with one current shift seeded. Operators add checklist notes. Admins create shifts. Viewers can read.
- Watchlist for a plate or a person label. A match creates an alert through the existing alert path and a match row. Seeded events do not store plate text (`metadata.plate` is only written by live plate detection), so the demo entry matches object class `person` (`metadata.object`) plus the label `Person detected`.

Viewers can read sites, alerts, policies, evidence, shifts, and the watchlist. Operators can acknowledge alerts, mark the outbox sent, send camera heartbeats, add shift notes, and add watchlist entries. Only admins create shifts, edit policies, or open the audit log.

## Tech stack

| Layer | Stack |
|-------|--------|
| Frontend | React, TypeScript, Vite, Tailwind CSS v4, Recharts, Zustand |
| Backend | FastAPI, SQLAlchemy, SQLite (Postgres-ready) |
| AI | Ultralytics YOLOv11n, ByteTrack, OpenCV |
| Streaming | OpenCV capture → MJPEG + MP4 segments |
| Auth | JWT (python-jose) + RBAC |

## Quick start (Windows)

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
$env:PYTHONPATH = "$((Get-Location).Path)\backend"
.\backend\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

First launch will:
- Create `storage/vms.db`
- Generate synthetic demo videos under `sample-data/videos/`
- Seed users, 4 cameras, zones, sample events
- Seed sites (HQ, Warehouse), two alert policies, alerts derived from those events, camera heartbeats, one current shift, and one person watchlist entry

Detection still starts if the YOLO weight file is not downloaded. The API boots, serves seeded events, and the operations features run on stored events. YOLO loads only when a live camera actually runs detection.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Demo accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@aethershield.io | admin123 |
| Operator | operator@aethershield.io | operator123 |
| Viewer | viewer@aethershield.io | viewer123 |

## API docs

With the backend running: http://127.0.0.1:8000/docs

## Project structure

```
A1 FENCE/
├── backend/app/          # FastAPI app (api, ai, services, models)
├── frontend/src/         # React UI
├── sample-data/videos/   # Demo MP4 sources
├── storage/              # DB, recordings, snapshots
├── docs/                 # Schema & architecture notes
└── docker-compose.yml    # Optional container deploy
```

## Optional webcam / RTSP

Create or patch a camera via API:

```json
{
  "name": "Webcam",
  "source_type": "webcam",
  "source_uri": "0",
  "ai_enabled": true
}
```

```json
{
  "name": "IP Cam",
  "source_type": "rtsp",
  "source_uri": "rtsp://user:pass@192.168.1.10/stream",
  "ai_enabled": true
}
```

## Acknowledgements

- [Ultralytics YOLOv11](https://github.com/ultralytics/ultralytics)
- [OpenCV](https://opencv.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/) / [Vite](https://vitejs.dev/) / [Tailwind CSS](https://tailwindcss.com/)
- [Recharts](https://recharts.org/)
- ByteTrack (via Ultralytics track mode)

## License

Academic / portfolio use for A-1 Launchpad 2026.
