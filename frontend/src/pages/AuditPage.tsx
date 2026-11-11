import { useQuery } from '@tanstack/react-query'
import { api, type AuditRow } from '@/lib/api'
import { formatTime } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth'

export function AuditPage() {
  const role = useAuthStore((s) => s.user?.role)
  const { data, error, isLoading } = useQuery({
    queryKey: ['audit'],
    queryFn: async () => (await api.get<AuditRow[]>('/api/audit')).data,
    enabled: role === 'admin',
    retry: false,
  })

  if (role && role !== 'admin') {
    return (
      <div className="rounded-xl border border-border bg-panel p-6 text-sm text-muted">
        The audit log is visible to admins only.
      </div>
    )
  }

  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
        <p className="text-sm text-muted mt-1">Latest 100 operator actions: login, alert acknowledge, incident status, policy edits</p>
      </div>
      <div className="rounded-xl border border-border bg-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-border bg-surface-2">
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Actor</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Target</th>
              <th className="px-4 py-3 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td className="px-4 py-6 text-muted" colSpan={5}>Loading audit log…</td></tr>
            )}
            {error && (
              <tr><td className="px-4 py-6 text-danger" colSpan={5}>Audit log is restricted to admins.</td></tr>
            )}
            {(data || []).map((row) => (
              <tr key={row.id} className="border-b border-border/50">
                <td className="px-4 py-2.5 font-mono text-xs text-muted whitespace-nowrap">{formatTime(row.ts)}</td>
                <td className="px-4 py-2.5">{row.actor}</td>
                <td className="px-4 py-2.5">{row.action}</td>
                <td className="px-4 py-2.5 font-mono text-xs">{row.target}</td>
                <td className="px-4 py-2.5 text-muted">{row.detail || '—'}</td>
              </tr>
            ))}
            {data && data.length === 0 && (
              <tr><td className="px-4 py-6 text-muted" colSpan={5}>No audit rows yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
