import { useQuery } from '@tanstack/react-query'
import { api, type DashboardStats } from '@/lib/api'
import { PRIORITY_COLOR, formatTime, cn } from '@/lib/utils'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar,
} from 'recharts'
import { Camera, AlertTriangle, HardDrive, Activity, Cpu, Wifi } from 'lucide-react'

export function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => (await api.get<DashboardStats>('/api/dashboard')).data,
    refetchInterval: 5000,
  })

  if (isLoading || !data) {
    return <div className="text-muted animate-pulse">Loading command center…</div>
  }

  const typeData = Object.entries(data.detections_by_type).map(([name, value]) => ({ name, value }))

  return (
    <div className="space-y-5 animate-fade-up">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Operations Dashboard</h1>
        <p className="text-sm text-muted mt-1">Live camera health, detections, and storage intelligence</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat icon={Camera} label="Cameras Online" value={`${data.online_cameras}/${data.total_cameras}`} accent="text-ok" />
        <Stat icon={Activity} label="Today's Detections" value={String(data.today_detections)} accent="text-accent" />
        <Stat icon={AlertTriangle} label="Active Alerts" value={String(data.active_alerts)} accent="text-danger" />
        <Stat
          icon={HardDrive}
          label="Storage Remaining"
          value={data.storage_days_remaining != null ? `${data.storage_days_remaining} days` : '—'}
          sub={`${data.storage_used_gb.toFixed(2)} / ${data.storage_total_gb} GB`}
          accent="text-info"
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-xl border border-border bg-panel p-4">
          <h2 className="text-sm font-medium mb-3">Weekly Detections</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.weekly_detections}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3dd6c6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3dd6c6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#8b9bb0" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#8b9bb0" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: '#121821', border: '1px solid #1e2836', borderRadius: 8 }}
                />
                <Area type="monotone" dataKey="count" stroke="#3dd6c6" fill="url(#g1)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-panel p-4">
          <h2 className="text-sm font-medium mb-3">Detections by Type</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={typeData}>
                <XAxis dataKey="name" stroke="#8b9bb0" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#8b9bb0" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#121821', border: '1px solid #1e2836', borderRadius: 8 }} />
                <Bar dataKey="value" fill="#4aa3ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-panel p-4">
          <h2 className="text-sm font-medium mb-3 flex items-center gap-2"><Cpu className="h-4 w-4 text-accent" /> System Health</h2>
          <Meter label="CPU" value={data.cpu_percent} />
          <Meter label="Memory" value={data.memory_percent} />
          <Meter label="Storage" value={(data.storage_used_gb / data.storage_total_gb) * 100} />
          <div className="mt-4 text-xs text-muted space-y-1">
            <div>Most active: <span className="text-ink">{String(data.insights.most_active_camera ?? '—')}</span></div>
            <div>Peak hour: <span className="text-ink">{data.insights.peak_hour != null ? `${data.insights.peak_hour}:00` : '—'}</span></div>
            <div>Avg / hour: <span className="text-ink">{String(data.insights.avg_per_hour ?? '—')}</span></div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-panel p-4">
          <h2 className="text-sm font-medium mb-3 flex items-center gap-2"><Wifi className="h-4 w-4 text-ok" /> Camera Health</h2>
          <div className="space-y-2 max-h-64 overflow-auto">
            {data.camera_health.map((c) => (
              <div key={c.id} className="flex items-center justify-between rounded-md border border-border bg-surface-2 px-3 py-2">
                <div>
                  <div className="text-sm">{c.name}</div>
                  <div className="text-[10px] text-muted">{c.resolution} · {Math.round(c.fps)} FPS</div>
                </div>
                <span className={cn(
                  'text-[10px] uppercase tracking-wider font-semibold',
                  c.status === 'offline' || c.status === 'error' ? 'text-danger' : 'text-ok',
                )}>
                  {c.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-panel p-4">
          <h2 className="text-sm font-medium mb-3">Active Alerts</h2>
          <div className="space-y-2 max-h-64 overflow-auto">
            {data.active_alerts_list.length === 0 && (
              <p className="text-sm text-muted">No active alerts</p>
            )}
            {data.active_alerts_list.map((a) => (
              <div key={a.id} className="rounded-md border border-border bg-surface-2 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: PRIORITY_COLOR[a.priority] }} />
                  <span className="text-sm font-medium truncate">{a.title}</span>
                </div>
                <div className="text-[10px] text-muted mt-1">{formatTime(a.created_at)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-panel p-4">
        <h2 className="text-sm font-medium mb-3">Recent AI Detections</h2>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-border">
                <th className="pb-2 font-medium">Time</th>
                <th className="pb-2 font-medium">Camera</th>
                <th className="pb-2 font-medium">Event</th>
                <th className="pb-2 font-medium">Priority</th>
                <th className="pb-2 font-medium">Conf</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_events.map((e) => (
                <tr key={e.id} className="border-b border-border/60">
                  <td className="py-2 font-mono text-xs text-muted">{formatTime(e.timestamp)}</td>
                  <td className="py-2">{e.camera_name}</td>
                  <td className="py-2">{e.label}</td>
                  <td className="py-2">
                    <span className="text-xs uppercase" style={{ color: PRIORITY_COLOR[e.priority] }}>{e.priority}</span>
                  </td>
                  <td className="py-2 font-mono text-xs">{(e.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Stat({
  icon: Icon, label, value, sub, accent,
}: {
  icon: typeof Camera
  label: string
  value: string
  sub?: string
  accent: string
}) {
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-muted">{label}</span>
        <Icon className={cn('h-4 w-4', accent)} />
      </div>
      <div className="text-2xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="text-[11px] text-muted mt-1">{sub}</div>}
    </div>
  )
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-muted">{label}</span>
        <span className="font-mono">{value.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
    </div>
  )
}
