import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, type EventItem, type EvidencePackage } from '@/lib/api'
import { PRIORITY_COLOR, formatTime } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { useState } from 'react'
import { toast } from 'sonner'

export function EventsPage() {
  const navigate = useNavigate()
  const [priority, setPriority] = useState('')
  const [eventType, setEventType] = useState('')
  const [selected, setSelected] = useState<EventItem | null>(null)
  const [evidence, setEvidence] = useState<EvidencePackage | null>(null)
  const [exporting, setExporting] = useState(false)

  const exportEvidence = async (event: EventItem) => {
    setSelected(event)
    setExporting(true)
    try {
      const { data } = await api.get<EvidencePackage>(`/api/events/${event.id}/evidence`)
      setEvidence(data)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `evidence-event-${event.id}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Could not export evidence')
    } finally {
      setExporting(false)
    }
  }

  const { data: events = [], refetch } = useQuery({
    queryKey: ['events', priority, eventType],
    queryFn: async () =>
      (await api.get<EventItem[]>('/api/events', {
        params: {
          hours: 72,
          limit: 200,
          ...(priority ? { priority } : {}),
          ...(eventType ? { event_type: eventType } : {}),
        },
      })).data,
    refetchInterval: 8000,
  })

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Events</h1>
          <p className="text-sm text-muted mt-1">AI detections with priority ranking</p>
        </div>
        <div className="flex gap-2">
          <select className="h-9 rounded-md border border-border bg-panel px-3 text-sm" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">All priorities</option>
            {['critical', 'high', 'medium', 'low'].map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <select className="h-9 rounded-md border border-border bg-panel px-3 text-sm" value={eventType} onChange={(e) => setEventType(e.target.value)}>
            <option value="">All types</option>
            {['person', 'car', 'intrusion', 'motion', 'bicycle', 'truck'].map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <Button variant="outline" size="sm" onClick={() => refetch()}>Refresh</Button>
        </div>
      </div>

      {selected && (
        <div className="rounded-xl border border-border bg-panel p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-medium">Event detail</h2>
              <p className="text-sm mt-1">{selected.label}</p>
              <p className="text-xs text-muted mt-1">
                {selected.camera_name} · {formatTime(selected.timestamp)}
                {selected.track_id != null ? ` · track #${selected.track_id}` : ''}
              </p>
            </div>
            <Button size="sm" onClick={() => exportEvidence(selected)} disabled={exporting}>
              {exporting ? 'Exporting…' : 'Export evidence'}
            </Button>
          </div>
          {evidence && evidence.event_id === selected.id && (
            <dl className="mt-4 grid sm:grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-muted">Camera</dt>
                <dd>{evidence.camera.name}{evidence.camera.site ? ` · ${evidence.camera.site}` : ''}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-muted">Zone</dt>
                <dd>{evidence.zone?.name || '—'}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-muted">Timestamp</dt>
                <dd className="font-mono text-xs">{formatTime(evidence.timestamp)}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-muted">Track id</dt>
                <dd className="font-mono text-xs">{evidence.track_id != null ? `#${evidence.track_id}` : '—'}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-[10px] uppercase tracking-wider text-muted">Clip window</dt>
                <dd className="text-muted">{evidence.clip_window_note}</dd>
              </div>
            </dl>
          )}
        </div>
      )}

      <div className="rounded-xl border border-border bg-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-border bg-surface-2">
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Camera</th>
              <th className="px-4 py-3 font-medium">Event</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Priority</th>
              <th className="px-4 py-3 font-medium">Conf</th>
              <th className="px-4 py-3 font-medium">Track</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr
                key={e.id}
                className={`border-b border-border/50 hover:bg-surface-2/50 cursor-pointer ${selected?.id === e.id ? 'bg-accent/5' : ''}`}
                onClick={() => { setSelected(e); if (evidence && evidence.event_id !== e.id) setEvidence(null) }}
              >
                <td className="px-4 py-2.5 font-mono text-xs text-muted whitespace-nowrap">{formatTime(e.timestamp)}</td>
                <td className="px-4 py-2.5">{e.camera_name}</td>
                <td className="px-4 py-2.5">{e.label}</td>
                <td className="px-4 py-2.5 text-muted">{e.event_type}</td>
                <td className="px-4 py-2.5">
                  <span className="text-xs uppercase font-semibold" style={{ color: PRIORITY_COLOR[e.priority] }}>{e.priority}</span>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">{(e.confidence * 100).toFixed(0)}%</td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">{e.track_id != null ? `#${e.track_id}` : '—'}</td>
                <td className="px-4 py-2.5 whitespace-nowrap">
                  <Button size="sm" variant="ghost" onClick={(ev) => { ev.stopPropagation(); exportEvidence(e) }}>
                    Export evidence
                  </Button>
                  <Button size="sm" variant="ghost" onClick={(ev) => { ev.stopPropagation(); navigate(`/playback?camera=${e.camera_id}&event=${e.id}`) }}>
                    Replay
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
