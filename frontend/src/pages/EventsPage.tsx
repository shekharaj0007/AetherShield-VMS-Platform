import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, type EventItem } from '@/lib/api'
import { PRIORITY_COLOR, formatTime } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { useState } from 'react'

export function EventsPage() {
  const navigate = useNavigate()
  const [priority, setPriority] = useState('')
  const [eventType, setEventType] = useState('')

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
              <tr key={e.id} className="border-b border-border/50 hover:bg-surface-2/50">
                <td className="px-4 py-2.5 font-mono text-xs text-muted whitespace-nowrap">{formatTime(e.timestamp)}</td>
                <td className="px-4 py-2.5">{e.camera_name}</td>
                <td className="px-4 py-2.5">{e.label}</td>
                <td className="px-4 py-2.5 text-muted">{e.event_type}</td>
                <td className="px-4 py-2.5">
                  <span className="text-xs uppercase font-semibold" style={{ color: PRIORITY_COLOR[e.priority] }}>{e.priority}</span>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">{(e.confidence * 100).toFixed(0)}%</td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">{e.track_id != null ? `#${e.track_id}` : '—'}</td>
                <td className="px-4 py-2.5">
                  <Button size="sm" variant="ghost" onClick={() => navigate(`/playback?camera=${e.camera_id}&event=${e.id}`)}>
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
