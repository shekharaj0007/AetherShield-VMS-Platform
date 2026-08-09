import { useQuery } from '@tanstack/react-query'
import { api, type Incident } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { formatTime, PRIORITY_COLOR } from '@/lib/utils'
import { useNavigate } from 'react-router-dom'

const STATUSES = ['open', 'investigating', 'resolved', 'false_alarm', 'escalated']

export function IncidentsPage() {
  const navigate = useNavigate()
  const { data: incidents = [], refetch } = useQuery({
    queryKey: ['incidents'],
    queryFn: async () => (await api.get<Incident[]>('/api/incidents')).data,
    refetchInterval: 10000,
  })

  const updateStatus = async (id: number, status: string) => {
    await api.patch(`/api/incidents/${id}`, { status })
    refetch()
  }

  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Incident Management</h1>
        <p className="text-sm text-muted mt-1">Investigate, escalate, and resolve security incidents</p>
      </div>

      <div className="grid gap-3">
        {incidents.map((inc) => (
          <div key={inc.id} className="rounded-xl border border-border bg-panel p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-medium">{inc.event?.label ?? `Incident #${inc.id}`}</div>
                <div className="text-xs text-muted mt-1">
                  {inc.event?.camera_name} · {formatTime(inc.created_at)}
                  {inc.event && (
                    <span className="ml-2 uppercase" style={{ color: PRIORITY_COLOR[inc.event.priority] }}>
                      {inc.event.priority}
                    </span>
                  )}
                </div>
                {inc.notes && <p className="text-sm text-muted mt-2">{inc.notes}</p>}
              </div>
              <div className="flex flex-wrap gap-2 items-center">
                <select
                  className="h-8 rounded-md border border-border bg-surface px-2 text-xs"
                  value={inc.status}
                  onChange={(e) => updateStatus(inc.id, e.target.value)}
                >
                  {STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                </select>
                {inc.event && (
                  <Button size="sm" variant="outline" onClick={() => navigate(`/playback?camera=${inc.event!.camera_id}&event=${inc.event_id}`)}>
                    Open evidence
                  </Button>
                )}
              </div>
            </div>
          </div>
        ))}
        {incidents.length === 0 && (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-muted text-sm">
            No incidents yet. Critical detections create incidents automatically.
          </div>
        )}
      </div>
    </div>
  )
}
