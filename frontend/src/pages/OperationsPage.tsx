import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  type AlertItem,
  type AlertPolicy,
  type OperatorOption,
  type OutboxRow,
  type Shift,
  type Site,
  type WatchEntry,
  type WatchHit,
} from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { PRIORITY_COLOR, formatTime } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth'
import { useState } from 'react'
import { toast } from 'sonner'

function ruleSummary(policy: AlertPolicy) {
  const cfg = policy.config || {}
  if (policy.rule_type === 'zone_after_hours') {
    return `Person or intrusion inside a zone after ${String(cfg.after || '21:00')} (server local time)`
  }
  if (policy.rule_type === 'loitering') {
    return `Same track id seen longer than ${String(cfg.min_seconds ?? 60)} seconds`
  }
  if (policy.rule_type === 'unknown_face') {
    return 'Unknown face (face_category = unknown)'
  }
  return policy.rule_type
}

export function OperationsPage() {
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'
  const isOperator = user?.role === 'operator'
  const canAck = user?.role === 'admin' || user?.role === 'operator'
  const canDeliver = canAck
  const canNote = canAck
  const canWatchWrite = canAck
  const qc = useQueryClient()

  const { data: sites = [] } = useQuery({
    queryKey: ['sites'],
    queryFn: async () => (await api.get<Site[]>('/api/sites')).data,
  })
  const { data: policies = [] } = useQuery({
    queryKey: ['policies'],
    queryFn: async () => (await api.get<AlertPolicy[]>('/api/policies')).data,
  })
  const { data: alerts = [] } = useQuery({
    queryKey: ['ops-alerts'],
    queryFn: async () => (await api.get<AlertItem[]>('/api/alerts')).data,
    refetchInterval: 10000,
  })
  const { data: outbox = [] } = useQuery({
    queryKey: ['outbox'],
    queryFn: async () => (await api.get<OutboxRow[]>('/api/outbox')).data,
  })
  const { data: shifts = [] } = useQuery({
    queryKey: ['shifts'],
    queryFn: async () => (await api.get<Shift[]>('/api/shifts')).data,
  })
  const { data: operators = [] } = useQuery({
    queryKey: ['shift-operators'],
    queryFn: async () => (await api.get<OperatorOption[]>('/api/shifts/operators')).data,
    enabled: isAdmin,
  })
  const { data: watchlist = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: async () => (await api.get<WatchEntry[]>('/api/watchlist')).data,
  })
  const { data: watchHits = [] } = useQuery({
    queryKey: ['watch-hits'],
    queryFn: async () => (await api.get<WatchHit[]>('/api/watchlist/hits')).data,
  })

  const [name, setName] = useState('Unknown face')
  const [ruleType, setRuleType] = useState('unknown_face')
  const [channel, setChannel] = useState<'webhook' | 'email'>('webhook')
  const [shiftSite, setShiftSite] = useState<number | ''>('')
  const [shiftOperator, setShiftOperator] = useState<number | ''>('')
  const [shiftStart, setShiftStart] = useState('')
  const [shiftEnd, setShiftEnd] = useState('')
  const [noteDrafts, setNoteDrafts] = useState<Record<number, string>>({})
  const [watchKind, setWatchKind] = useState<'person' | 'plate'>('person')
  const [watchValue, setWatchValue] = useState('')

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['policies'] })
    qc.invalidateQueries({ queryKey: ['ops-alerts'] })
    qc.invalidateQueries({ queryKey: ['outbox'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['shifts'] })
    qc.invalidateQueries({ queryKey: ['watchlist'] })
    qc.invalidateQueries({ queryKey: ['watch-hits'] })
  }

  const savePolicy = useMutation({
    mutationFn: async (policy: AlertPolicy) =>
      (await api.patch(`/api/policies/${policy.id}`, {
        enabled: policy.enabled,
        config: policy.config,
        notify_channel: policy.notify_channel,
        name: policy.name,
      })).data,
    onSuccess: () => {
      toast.success('Policy saved')
      refresh()
    },
    onError: () => toast.error('Only admins can edit policies'),
  })

  const createPolicy = useMutation({
    mutationFn: async () =>
      (await api.post('/api/policies', {
        name,
        rule_type: ruleType,
        notify_channel: channel,
        enabled: true,
      })).data,
    onSuccess: () => {
      toast.success('Policy created and evaluated against stored events')
      refresh()
    },
    onError: () => toast.error('Could not create policy'),
  })

  const acknowledge = useMutation({
    mutationFn: async (id: number) => (await api.post(`/api/alerts/${id}/acknowledge`)).data,
    onSuccess: () => {
      toast.success('Alert acknowledged')
      refresh()
    },
    onError: () => toast.error('Operators acknowledge alerts'),
  })

  const createShift = useMutation({
    mutationFn: async () =>
      (await api.post('/api/shifts', {
        site_id: Number(shiftSite),
        operator_id: Number(shiftOperator),
        starts_at: new Date(shiftStart).toISOString(),
        ends_at: new Date(shiftEnd).toISOString(),
      })).data,
    onSuccess: () => {
      toast.success('Shift created')
      setShiftStart('')
      setShiftEnd('')
      refresh()
    },
    onError: () => toast.error('Only admins can create shifts'),
  })

  const addNote = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: string }) =>
      (await api.post(`/api/shifts/${id}/notes`, { body })).data,
    onSuccess: (_data, vars) => {
      toast.success('Checklist note added')
      setNoteDrafts((prev) => ({ ...prev, [vars.id]: '' }))
      refresh()
    },
    onError: () => toast.error('Operators add checklist notes'),
  })

  const createWatch = useMutation({
    mutationFn: async () =>
      (await api.post('/api/watchlist', { kind: watchKind, value: watchValue.trim() })).data,
    onSuccess: () => {
      toast.success('Watchlist entry saved and matched against stored events')
      setWatchValue('')
      refresh()
    },
    onError: () => toast.error('Could not add watchlist entry'),
  })

  const deliver = useMutation({
    mutationFn: async () => (await api.post('/api/outbox/deliver')).data as { delivered: number },
    onSuccess: (data) => {
      toast.success(`Marked ${data.delivered} notification(s) sent`)
      refresh()
    },
    onError: () => toast.error('Could not deliver outbox'),
  })

  return (
    <div className="space-y-5 animate-fade-up">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Operations</h1>
        <p className="text-sm text-muted mt-1">
          Sites, shifts, watchlist, alert policies, acknowledgements, and the notification outbox
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        {sites.map((site) => (
          <div key={site.id} className="rounded-xl border border-border bg-panel px-4 py-3">
            <div className="text-[10px] uppercase tracking-wider text-accent">{site.code}</div>
            <div className="font-medium mt-1">{site.name}</div>
            <div className="text-xs text-muted mt-1">{site.camera_count} cameras · {site.address || 'No address'}</div>
          </div>
        ))}
      </div>

      <section className="rounded-xl border border-border bg-panel p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium">Shifts</h2>
            <p className="text-[11px] text-muted mt-1">
              {isAdmin ? 'Admins create shifts.' : isOperator ? 'Add a checklist note on a shift.' : 'Read only.'}
            </p>
          </div>
        </div>
        <div className="space-y-3">
          {shifts.map((shift) => (
            <div key={shift.id} className="rounded-lg border border-border bg-surface-2 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-medium">
                    {shift.site_name || 'Site'} · {shift.operator_name || shift.operator_email}
                  </div>
                  <div className="text-xs text-muted mt-1">
                    {formatTime(shift.starts_at)} → {formatTime(shift.ends_at)}
                  </div>
                </div>
                {shift.current && (
                  <span className="text-[10px] uppercase tracking-wider text-ok">Current</span>
                )}
              </div>
              <ul className="mt-2 space-y-1">
                {shift.notes.map((note) => (
                  <li key={note.id} className="text-xs text-muted">
                    <span className="text-ink">{note.body}</span>
                    {' · '}{note.author_name || 'operator'} · {formatTime(note.created_at)}
                  </li>
                ))}
                {shift.notes.length === 0 && <li className="text-xs text-muted">No checklist notes yet.</li>}
              </ul>
              {canNote && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <input
                    className="h-8 flex-1 min-w-[12rem] rounded-md border border-border bg-surface px-2 text-sm text-ink"
                    placeholder="Checklist note"
                    value={noteDrafts[shift.id] || ''}
                    onChange={(e) => setNoteDrafts((prev) => ({ ...prev, [shift.id]: e.target.value }))}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={addNote.isPending || !(noteDrafts[shift.id] || '').trim()}
                    onClick={() => addNote.mutate({ id: shift.id, body: noteDrafts[shift.id] || '' })}
                  >
                    Add note
                  </Button>
                </div>
              )}
            </div>
          ))}
          {shifts.length === 0 && <p className="text-sm text-muted">No shifts yet.</p>}
        </div>
        {isAdmin && (
          <div className="flex flex-wrap gap-2 items-end border-t border-border pt-3">
            <label className="text-xs text-muted">
              Site
              <select
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-3 text-sm text-ink"
                value={shiftSite}
                onChange={(e) => setShiftSite(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">Select</option>
                {sites.map((site) => (
                  <option key={site.id} value={site.id}>{site.name}</option>
                ))}
              </select>
            </label>
            <label className="text-xs text-muted">
              Operator
              <select
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-3 text-sm text-ink"
                value={shiftOperator}
                onChange={(e) => setShiftOperator(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">Select</option>
                {operators.map((op) => (
                  <option key={op.id} value={op.id}>{op.full_name}</option>
                ))}
              </select>
            </label>
            <label className="text-xs text-muted">
              Start
              <input
                type="datetime-local"
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-2 text-sm text-ink"
                value={shiftStart}
                onChange={(e) => setShiftStart(e.target.value)}
              />
            </label>
            <label className="text-xs text-muted">
              End
              <input
                type="datetime-local"
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-2 text-sm text-ink"
                value={shiftEnd}
                onChange={(e) => setShiftEnd(e.target.value)}
              />
            </label>
            <Button
              size="sm"
              disabled={createShift.isPending || !shiftSite || !shiftOperator || !shiftStart || !shiftEnd}
              onClick={() => createShift.mutate()}
            >
              Add shift
            </Button>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-panel p-4 space-y-3">
        <div>
          <h2 className="text-sm font-medium">Watchlist</h2>
          <p className="text-[11px] text-muted mt-1">
            A plate matches metadata.plate. Seeded events have no plate text, so the demo entry matches object class person plus the label “Person detected”. Matches create an alert on the existing alert path.
          </p>
        </div>
        <div className="space-y-2">
          {watchlist.map((entry) => (
            <div key={entry.id} className="rounded-lg border border-border bg-surface-2 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider text-accent">{entry.kind}</span>
                <span className="text-sm font-medium">{entry.value}</span>
                <span className="text-[10px] text-muted ml-auto">{entry.match_count} match{entry.match_count === 1 ? '' : 'es'}</span>
              </div>
              {entry.note && <p className="text-xs text-muted mt-1">{entry.note}</p>}
            </div>
          ))}
          {watchlist.length === 0 && <p className="text-sm text-muted">No watchlist entries.</p>}
        </div>
        {watchHits.length > 0 && (
          <div className="text-xs text-muted space-y-1">
            {watchHits.slice(0, 6).map((hit) => (
              <div key={hit.id}>
                {hit.value} → {hit.event_label} · alert #{hit.alert_id ?? '—'} · {formatTime(hit.created_at)}
              </div>
            ))}
          </div>
        )}
        {canWatchWrite && (
          <div className="flex flex-wrap gap-2 items-end border-t border-border pt-3">
            <label className="text-xs text-muted">
              Kind
              <select
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-3 text-sm text-ink"
                value={watchKind}
                onChange={(e) => setWatchKind(e.target.value as 'person' | 'plate')}
              >
                <option value="person">person label</option>
                <option value="plate">plate</option>
              </select>
            </label>
            <label className="text-xs text-muted">
              Value
              <input
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-3 text-sm text-ink"
                placeholder={watchKind === 'plate' ? 'DL10AB2424' : 'Person detected'}
                value={watchValue}
                onChange={(e) => setWatchValue(e.target.value)}
              />
            </label>
            <Button size="sm" disabled={createWatch.isPending || !watchValue.trim()} onClick={() => createWatch.mutate()}>
              Add to watchlist
            </Button>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-panel p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium">Alert policies</h2>
          <span className="text-[10px] uppercase tracking-wider text-muted">
            {isAdmin ? 'Admin can edit' : 'Read only'}
          </span>
        </div>
        <div className="space-y-3">
          {policies.map((policy) => (
            <PolicyRow
              key={`${policy.id}-${policy.updated_at}`}
              policy={policy}
              locked={!isAdmin}
              pending={savePolicy.isPending}
              onSave={(next) => savePolicy.mutate(next)}
            />
          ))}
          {policies.length === 0 && <p className="text-sm text-muted">No policies stored.</p>}
        </div>
        {isAdmin && (
          <div className="flex flex-wrap gap-2 items-end border-t border-border pt-3">
            <label className="text-xs text-muted">
              Name
              <input
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-3 text-sm text-ink"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="text-xs text-muted">
              Rule
              <select
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-3 text-sm text-ink"
                value={ruleType}
                onChange={(e) => setRuleType(e.target.value)}
              >
                <option value="zone_after_hours">Person in a zone after 21:00</option>
                <option value="loitering">Loitering (same track id)</option>
                <option value="unknown_face">Unknown face</option>
              </select>
            </label>
            <label className="text-xs text-muted">
              Channel
              <select
                className="mt-1 block h-9 rounded-md border border-border bg-surface px-3 text-sm text-ink"
                value={channel}
                onChange={(e) => setChannel(e.target.value as 'webhook' | 'email')}
              >
                <option value="webhook">webhook</option>
                <option value="email">email</option>
              </select>
            </label>
            <Button size="sm" onClick={() => createPolicy.mutate()} disabled={createPolicy.isPending || !name.trim()}>
              Add policy
            </Button>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-panel overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-medium">Alerts</h2>
        </div>
        <div className="divide-y divide-border/60">
          {alerts.map((alert) => (
            <div key={alert.id} className="px-4 py-3 flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: PRIORITY_COLOR[alert.priority] || '#8b9bb0' }} />
                  <span className="text-sm font-medium">{alert.title}</span>
                  {alert.policy_id != null && (
                    <span className="text-[10px] uppercase tracking-wider text-accent">policy</span>
                  )}
                </div>
                <p className="text-xs text-muted mt-1 max-w-xl">{alert.message}</p>
                <div className="text-[10px] text-muted mt-1">{formatTime(alert.created_at)}</div>
              </div>
              {alert.acknowledged || !alert.is_active ? (
                <span className="text-[10px] uppercase tracking-wider text-ok">Acknowledged</span>
              ) : canAck ? (
                <Button size="sm" variant="outline" onClick={() => acknowledge.mutate(alert.id)}>
                  Acknowledge
                </Button>
              ) : (
                <span className="text-[10px] uppercase tracking-wider text-muted">Active</span>
              )}
            </div>
          ))}
          {alerts.length === 0 && <p className="px-4 py-6 text-sm text-muted">No alerts yet.</p>}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-panel overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium">Notification outbox</h2>
            <p className="text-[11px] text-muted mt-1">Simulated delivery. Nothing is sent to the internet.</p>
          </div>
          {canDeliver && (
            <Button size="sm" variant="outline" onClick={() => deliver.mutate()} disabled={deliver.isPending}>
              Mark pending sent
            </Button>
          )}
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-border bg-surface-2">
              <th className="px-4 py-2 font-medium">When</th>
              <th className="px-4 py-2 font-medium">Channel</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Payload</th>
            </tr>
          </thead>
          <tbody>
            {outbox.map((row) => (
              <tr key={row.id} className="border-b border-border/50">
                <td className="px-4 py-2 font-mono text-xs text-muted whitespace-nowrap">{formatTime(row.created_at)}</td>
                <td className="px-4 py-2">{row.channel}</td>
                <td className="px-4 py-2">
                  <span className={row.status === 'sent' ? 'text-ok' : 'text-warn'}>{row.status}</span>
                </td>
                <td className="px-4 py-2 text-xs text-muted truncate max-w-[280px]">
                  {String(row.payload?.title || row.payload?.message || '')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

function PolicyRow({
  policy, locked, pending, onSave,
}: {
  policy: AlertPolicy
  locked: boolean
  pending: boolean
  onSave: (policy: AlertPolicy) => void
}) {
  const [enabled, setEnabled] = useState(policy.enabled)
  const [after, setAfter] = useState(String(policy.config.after || '21:00'))
  const [minSeconds, setMinSeconds] = useState(Number(policy.config.min_seconds || 60))
  const [notify, setNotify] = useState(policy.notify_channel)

  return (
    <div className="rounded-lg border border-border bg-surface-2 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium">{policy.name}</div>
          <div className="text-xs text-muted mt-1">{ruleSummary({ ...policy, config: { ...policy.config, after, min_seconds: minSeconds } })}</div>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted">
          <input type="checkbox" checked={enabled} disabled={locked} onChange={(e) => setEnabled(e.target.checked)} />
          Enabled
        </label>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 items-end">
        {policy.rule_type === 'zone_after_hours' && (
          <label className="text-xs text-muted">
            After
            <input
              type="time"
              className="mt-1 block h-8 rounded-md border border-border bg-surface px-2 text-sm text-ink"
              value={after.length === 5 ? after : '21:00'}
              disabled={locked}
              onChange={(e) => setAfter(e.target.value)}
            />
          </label>
        )}
        {policy.rule_type === 'loitering' && (
          <label className="text-xs text-muted">
            Seconds
            <input
              type="number"
              min={1}
              className="mt-1 block h-8 w-24 rounded-md border border-border bg-surface px-2 text-sm text-ink"
              value={minSeconds}
              disabled={locked}
              onChange={(e) => setMinSeconds(Number(e.target.value))}
            />
          </label>
        )}
        <label className="text-xs text-muted">
          Channel
          <select
            className="mt-1 block h-8 rounded-md border border-border bg-surface px-2 text-sm text-ink"
            value={notify}
            disabled={locked}
            onChange={(e) => setNotify(e.target.value)}
          >
            <option value="webhook">webhook</option>
            <option value="email">email</option>
          </select>
        </label>
        {!locked && (
          <Button
            size="sm"
            variant="outline"
            disabled={pending}
            onClick={() => onSave({
              ...policy,
              enabled,
              notify_channel: notify,
              config: {
                ...policy.config,
                ...(policy.rule_type === 'zone_after_hours' ? { after } : {}),
                ...(policy.rule_type === 'loitering' ? { min_seconds: minSeconds } : {}),
              },
            })}
          >
            Save
          </Button>
        )}
      </div>
    </div>
  )
}
