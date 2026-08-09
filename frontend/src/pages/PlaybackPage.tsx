import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  api, recordingUrl, streamUrl, type Camera, type EventItem, type Recording, type Zone,
} from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { EventTimeline } from '@/components/EventTimeline'
import { Button } from '@/components/ui/Button'
import { formatTime, cn } from '@/lib/utils'
import {
  Pause, Play, SkipBack, SkipForward, Camera as CamIcon, Download,
} from 'lucide-react'

export function PlaybackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.token) || ''
  const initialCam = Number(params.get('camera') || 0) || null
  const eventId = Number(params.get('event') || 0) || null

  const [cameraId, setCameraId] = useState<number | null>(initialCam)
  const [mode, setMode] = useState<'live' | 'playback'>('live')
  const [speed, setSpeed] = useState(1)
  const [drawing, setDrawing] = useState(false)
  const [showHeatmap, setShowHeatmap] = useState(false)
  const [zoneDraft, setZoneDraft] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  const { data: cameras = [] } = useQuery({
    queryKey: ['cameras'],
    queryFn: async () => (await api.get<Camera[]>('/api/cameras')).data,
  })

  useEffect(() => {
    if (!cameraId && cameras[0]) setCameraId(cameras[0].id)
  }, [cameras, cameraId])

  const { data: events = [], refetch: refetchEvents } = useQuery({
    queryKey: ['timeline', cameraId],
    enabled: !!cameraId,
    queryFn: async () => (await api.get<EventItem[]>(`/api/events/timeline/${cameraId}`)).data,
    refetchInterval: 10000,
  })

  const { data: recordings = [] } = useQuery({
    queryKey: ['recordings', cameraId],
    enabled: !!cameraId,
    queryFn: async () => (await api.get<Recording[]>('/api/recordings', { params: { camera_id: cameraId } })).data,
  })

  const { data: zones = [], refetch: refetchZones } = useQuery({
    queryKey: ['zones', cameraId],
    enabled: !!cameraId,
    queryFn: async () => (await api.get<Zone[]>(`/api/cameras/${cameraId}/zones`)).data,
  })

  const activeRecording = recordings[0]
  const camera = cameras.find((c) => c.id === cameraId)

  useEffect(() => {
    if (!eventId) return
    api.get(`/api/recordings/by-event/${eventId}`).then(({ data }) => {
      setMode('playback')
      if (data.recording) {
        setCameraId(data.recording.camera_id)
        setTimeout(() => {
          if (videoRef.current) {
            videoRef.current.currentTime = data.seek_seconds || 0
            videoRef.current.play().catch(() => {})
          }
        }, 400)
      }
    })
  }, [eventId])

  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = speed
  }, [speed])

  const onEventClick = async (ev: EventItem) => {
    navigate(`/playback?camera=${ev.camera_id}&event=${ev.id}`)
    setCameraId(ev.camera_id)
    setMode('playback')
    const { data } = await api.get(`/api/recordings/by-event/${ev.id}`)
    if (data.recording && videoRef.current) {
      videoRef.current.src = recordingUrl(data.recording.id, token)
      videoRef.current.currentTime = data.seek_seconds || 0
      await videoRef.current.play().catch(() => {})
    }
  }

  const relPos = (e: React.MouseEvent) => {
    const rect = overlayRef.current!.getBoundingClientRect()
    return {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
    }
  }

  const saveZone = async () => {
    if (!cameraId || !zoneDraft || zoneDraft.w < 0.02 || zoneDraft.h < 0.02) return
    await api.post(`/api/cameras/${cameraId}/zones`, {
      name: `Zone ${zones.length + 1}`,
      shape: 'rectangle',
      geometry: zoneDraft,
      sensitivity: 0.6,
      enabled: true,
      trigger_classes: ['person'],
      color: '#ef4444',
    })
    setZoneDraft(null)
    setDrawing(false)
    refetchZones()
  }

  const selectedEvent = useMemo(
    () => events.find((e) => e.id === eventId) || null,
    [events, eventId],
  )

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Playback & Investigation</h1>
          <p className="text-sm text-muted mt-1">Timeline-linked recordings with detection zones</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className="h-9 rounded-md border border-border bg-panel px-3 text-sm"
            value={cameraId ?? ''}
            onChange={(e) => setCameraId(Number(e.target.value))}
          >
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <Button variant={mode === 'live' ? 'primary' : 'outline'} size="sm" onClick={() => setMode('live')}>Live</Button>
          <Button variant={mode === 'playback' ? 'primary' : 'outline'} size="sm" onClick={() => setMode('playback')}>Playback</Button>
          <Button variant={drawing ? 'danger' : 'outline'} size="sm" onClick={() => setDrawing((d) => !d)}>
            {drawing ? 'Drawing zone…' : 'Draw Zone'}
          </Button>
          <Button variant={showHeatmap ? 'primary' : 'outline'} size="sm" onClick={() => setShowHeatmap((v) => !v)}>
            Heatmap
          </Button>
          {zoneDraft && <Button size="sm" onClick={saveZone}>Save Zone</Button>}
          {eventId && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const url = `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/api/advanced/clips/export/${eventId}?token=${encodeURIComponent(token)}&before=10&after=20`
                window.open(url, '_blank')
              }}
            >
              Export clip
            </Button>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-4">
        <div>
          <div
            ref={overlayRef}
            className="relative aspect-video rounded-xl overflow-hidden border border-border bg-black"
            onMouseDown={(e) => {
              if (!drawing) return
              const p = relPos(e)
              setDragStart(p)
              setZoneDraft({ x: p.x, y: p.y, w: 0, h: 0 })
            }}
            onMouseMove={(e) => {
              if (!drawing || !dragStart) return
              const p = relPos(e)
              setZoneDraft({
                x: Math.min(dragStart.x, p.x),
                y: Math.min(dragStart.y, p.y),
                w: Math.abs(p.x - dragStart.x),
                h: Math.abs(p.y - dragStart.y),
              })
            }}
            onMouseUp={() => setDragStart(null)}
          >
            {mode === 'live' && cameraId ? (
              <img src={streamUrl(cameraId, token)} className="h-full w-full object-contain" alt="live" />
            ) : activeRecording ? (
              <video
                ref={videoRef}
                key={activeRecording.id}
                src={recordingUrl(activeRecording.id, token)}
                className="h-full w-full object-contain"
                controls={false}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-muted">No recording available</div>
            )}

            {showHeatmap && cameraId && (
              <img
                src={`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/api/advanced/heatmap/${cameraId}?token=${encodeURIComponent(token)}&t=${Date.now()}`}
                className="absolute inset-0 h-full w-full object-contain opacity-55 pointer-events-none mix-blend-screen"
                alt="heatmap"
              />
            )}
            {/* Zones overlay */}
            {zones.filter((z) => z.enabled).map((z) => {
              if (z.shape !== 'rectangle') return null
              const g = z.geometry as { x: number; y: number; w: number; h: number }
              return (
                <div
                  key={z.id}
                  className="absolute border-2 pointer-events-none"
                  style={{
                    left: `${g.x * 100}%`,
                    top: `${g.y * 100}%`,
                    width: `${g.w * 100}%`,
                    height: `${g.h * 100}%`,
                    borderColor: z.color,
                    background: `${z.color}22`,
                  }}
                >
                  <span className="absolute -top-5 left-0 text-[10px] px-1 rounded" style={{ background: z.color }}>{z.name}</span>
                </div>
              )
            })}
            {zoneDraft && (
              <div
                className="absolute border-2 border-dashed border-accent bg-accent/10 pointer-events-none"
                style={{
                  left: `${zoneDraft.x * 100}%`,
                  top: `${zoneDraft.y * 100}%`,
                  width: `${zoneDraft.w * 100}%`,
                  height: `${zoneDraft.h * 100}%`,
                }}
              />
            )}
            {selectedEvent?.bbox && mode === 'playback' && (
              <div
                className="absolute border-2 border-danger pointer-events-none"
                style={{
                  left: `${selectedEvent.bbox.x * 100}%`,
                  top: `${selectedEvent.bbox.y * 100}%`,
                  width: `${selectedEvent.bbox.w * 100}%`,
                  height: `${selectedEvent.bbox.h * 100}%`,
                }}
              />
            )}
          </div>

          {mode === 'playback' && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-panel p-2">
              <Button size="sm" variant="ghost" onClick={() => { if (videoRef.current) videoRef.current.currentTime -= 5 }}><SkipBack className="h-4 w-4" /></Button>
              <Button size="sm" variant="outline" onClick={() => {
                const v = videoRef.current
                if (!v) return
                if (v.paused) v.play()
                else v.pause()
              }}>
                <Play className="h-4 w-4" /> / <Pause className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { if (videoRef.current) videoRef.current.currentTime += 5 }}><SkipForward className="h-4 w-4" /></Button>
              {[0.5, 1, 2].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={cn('h-8 px-2 rounded text-xs', speed === s ? 'bg-accent text-surface' : 'text-muted')}
                >
                  {s}x
                </button>
              ))}
              <Button size="sm" variant="ghost" onClick={() => {
                const canvas = document.createElement('canvas')
                const v = videoRef.current
                if (!v) return
                canvas.width = v.videoWidth
                canvas.height = v.videoHeight
                canvas.getContext('2d')?.drawImage(v, 0, 0)
                const a = document.createElement('a')
                a.href = canvas.toDataURL('image/jpeg')
                a.download = 'snapshot.jpg'
                a.click()
              }}>
                <CamIcon className="h-4 w-4" /> Snapshot
              </Button>
              {activeRecording && (
                <a className="inline-flex items-center gap-1 text-xs text-muted hover:text-accent ml-auto" href={recordingUrl(activeRecording.id, token)} download>
                  <Download className="h-3.5 w-3.5" /> Download
                </a>
              )}
            </div>
          )}

          <div className="mt-4 rounded-xl border border-border bg-panel p-4">
            <EventTimeline events={events} onSelect={onEventClick} selectedId={eventId} />
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-xl border border-border bg-panel p-4">
            <h2 className="text-sm font-medium mb-2">{camera?.name ?? 'Camera'}</h2>
            <p className="text-xs text-muted">{camera?.location}</p>
            <p className="text-[11px] font-mono text-muted mt-2">{camera?.resolution} · AI {camera?.ai_enabled ? 'ON' : 'OFF'}</p>
          </div>
          <div className="rounded-xl border border-border bg-panel p-4">
            <h2 className="text-sm font-medium mb-3">Detection Zones</h2>
            <div className="space-y-2 max-h-40 overflow-auto">
              {zones.map((z) => (
                <div key={z.id} className="flex items-center justify-between text-xs rounded border border-border px-2 py-1.5">
                  <span className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: z.color }} />
                    {z.name}
                  </span>
                  <button
                    className="text-muted hover:text-ink"
                    onClick={async () => {
                      await api.patch(`/api/cameras/${cameraId}/zones/${z.id}`, { enabled: !z.enabled })
                      refetchZones()
                    }}
                  >
                    {z.enabled ? 'On' : 'Off'}
                  </button>
                </div>
              ))}
              {zones.length === 0 && <p className="text-xs text-muted">No zones — draw one on the feed</p>}
            </div>
          </div>
          <div className="rounded-xl border border-border bg-panel p-4">
            <h2 className="text-sm font-medium mb-3">Event List</h2>
            <div className="space-y-2 max-h-[420px] overflow-auto">
              {[...events].reverse().map((ev) => (
                <button
                  key={ev.id}
                  onClick={() => onEventClick(ev)}
                  className={cn(
                    'w-full text-left rounded-md border border-border bg-surface-2 px-3 py-2 hover:border-accent/40 transition-colors',
                    eventId === ev.id && 'border-accent/50 bg-accent/5',
                  )}
                >
                  <div className="text-sm font-medium truncate">{ev.label}</div>
                  <div className="text-[10px] text-muted mt-0.5">{formatTime(ev.timestamp)} · {(ev.confidence * 100).toFixed(0)}%</div>
                </button>
              ))}
            </div>
            <Button size="sm" variant="ghost" className="mt-2 w-full" onClick={() => refetchEvents()}>Refresh</Button>
          </div>
        </div>
      </div>
    </div>
  )
}
