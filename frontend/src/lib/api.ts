import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export const api = axios.create({
  baseURL: API_BASE,
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(err)
  },
)

export function streamUrl(cameraId: number, token: string) {
  return `${API_BASE}/api/stream/${cameraId}/mjpeg?token=${encodeURIComponent(token)}`
}

export function recordingUrl(recordingId: number, token: string) {
  return `${API_BASE}/api/recordings/${recordingId}/video?token=${encodeURIComponent(token)}`
}

export function mediaUrl(path: string, token: string) {
  return `${API_BASE}/api/media/snapshot?path=${encodeURIComponent(path)}&token=${encodeURIComponent(token)}`
}

export type Camera = {
  id: number
  name: string
  location: string
  source_type: string
  source_uri: string
  status: string
  resolution: string
  fps: number
  is_recording: boolean
  ai_enabled: boolean
  map_x: number
  map_y: number
  thumbnail_path?: string | null
  is_demo?: boolean
  enabled?: boolean
}

export type Zone = {
  id: number
  camera_id: number
  name: string
  shape: string
  geometry: Record<string, unknown>
  sensitivity: number
  enabled: boolean
  trigger_classes: string[]
  color: string
}

export type EventItem = {
  id: number
  camera_id: number
  zone_id?: number | null
  event_type: string
  label: string
  confidence: number
  priority: string
  track_id?: number | null
  bbox?: { x: number; y: number; w: number; h: number } | null
  snapshot_path?: string | null
  metadata_json?: Record<string, unknown> | null
  timestamp: string
  acknowledged: boolean
  camera_name?: string | null
}

export type DashboardStats = {
  total_cameras: number
  online_cameras: number
  offline_cameras: number
  today_detections: number
  active_alerts: number
  storage_used_gb: number
  storage_total_gb: number
  storage_days_remaining?: number | null
  cpu_percent: number
  memory_percent: number
  detections_by_type: Record<string, number>
  weekly_detections: { date: string; count: number }[]
  recent_events: EventItem[]
  camera_health: Camera[]
  active_alerts_list: {
    id: number
    title: string
    message: string
    priority: string
    created_at: string
    camera_id?: number
  }[]
  insights: Record<string, unknown>
}

export type Incident = {
  id: number
  event_id: number
  status: string
  assigned_to?: number | null
  notes: string
  created_at: string
  updated_at: string
  event?: EventItem | null
}

export type Recording = {
  id: number
  camera_id: number
  file_path: string
  start_time: string
  end_time?: string | null
  duration_seconds: number
  file_size_bytes: number
  resolution: string
}
