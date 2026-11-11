import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type AlertItem, type AlertPolicy, type OutboxRow, type Site } from '@/lib/api'
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
  const canAck = user?.role === 'admin' || user?.role === 'operator'
  const canDeliver = canAck
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

  const [name, setName] = useState('Unknown face')
  const [ruleType, setRuleType] = useState('unknown_face')
  const [channel, setChannel] = useState<'webhook' | 'email'>('webhook')

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['policies'] })
    qc.invalidateQueries({ queryKey: ['ops-alerts'] })
    qc.invalidateQueries({ queryKey: ['outbox'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
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
          Sites, alert policies, acknowledgements, and the notification outbox
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
