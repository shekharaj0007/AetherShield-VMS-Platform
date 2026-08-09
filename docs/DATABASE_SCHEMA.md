# Database Schema

SQLite by default (`storage/vms.db`). SQLAlchemy models map 1:1.

## ER overview

```
users ──┐
        │
cameras ┬── detection_zones
        ├── events ── incidents
        │         └── alerts
        └── recordings
```

## Tables

### users
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| email | VARCHAR unique | login |
| full_name | VARCHAR | |
| hashed_password | VARCHAR | bcrypt |
| role | VARCHAR | admin / operator / viewer |
| is_active | BOOLEAN | |
| created_at | DATETIME | |

### cameras
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name, location | VARCHAR | |
| source_type | VARCHAR | file / webcam / rtsp |
| source_uri | VARCHAR | path, index, or URL |
| status | VARCHAR | online / offline / recording / error |
| resolution, fps | | health metrics |
| ai_enabled, is_recording | BOOLEAN | |
| map_x, map_y | FLOAT | floor-plan coords 0–1 |

### detection_zones
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| camera_id | FK cameras | |
| name, shape | VARCHAR | rectangle / polygon / circle / freehand |
| geometry | JSON | normalized coords |
| sensitivity | FLOAT | 0–1 |
| enabled | BOOLEAN | |
| trigger_classes | JSON | empty = all |
| color | VARCHAR | hex |

### events
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| camera_id | FK | indexed |
| zone_id | FK nullable | |
| event_type | VARCHAR | person, car, intrusion, … |
| label | VARCHAR | display string |
| confidence | FLOAT | |
| priority | VARCHAR | critical/high/medium/low |
| track_id | INTEGER | ByteTrack ID |
| bbox | JSON | normalized x,y,w,h |
| snapshot_path | VARCHAR | |
| metadata_json | JSON | |
| timestamp | DATETIME | indexed |
| acknowledged | BOOLEAN | |

### recordings
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| camera_id | FK | |
| file_path | VARCHAR | relative to project root |
| start_time, end_time | DATETIME | |
| duration_seconds | FLOAT | |
| file_size_bytes | INTEGER | |

### incidents
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| event_id | FK unique | |
| status | VARCHAR | open / investigating / resolved / false_alarm / escalated |
| assigned_to | FK users | |
| notes | TEXT | |
| created_at, updated_at | DATETIME | |

### alerts
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| event_id, camera_id | FK nullable | |
| title, message | | |
| priority | VARCHAR | |
| is_active | BOOLEAN | |
| created_at | DATETIME | |
