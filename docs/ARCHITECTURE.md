# Architecture

```
Cameras (file / webcam / RTSP)
        │
        ▼
 OpenCV Capture Thread (per camera)
        │
        ├──► MJPEG live stream ──► Frontend Live Grid
        │
        ├──► YOLOv11 + ByteTrack
        │         │
        │         ├── bbox + track ID overlay
        │         └── zone intrusion check
        │                   │
        │                   ▼
        │              Event DB (+ Alert / Incident)
        │
        └──► MP4 segment writer ──► Recordings table
                    │
                    ▼
         Timeline + Playback seek (event → −10s)
                    │
                    ▼
     Dashboard / AI Search / Chat / PDF Report
```

## Key modules

- `backend/app/services/stream_manager.py` — capture, record, MJPEG
- `backend/app/ai/detector.py` — YOLO, tracking, zones, motion fallback
- `backend/app/services/ai_search.py` — NL parse, summary, chat RAG
- `frontend/src/pages/*` — Dashboard, Live, Playback, Search, Chat, Map, Incidents

## Security

- JWT bearer tokens
- RBAC permissions per role
- Stream URLs accept `?token=` for `<img>`/`<video>` tags
- Path traversal guard on snapshot media endpoint
