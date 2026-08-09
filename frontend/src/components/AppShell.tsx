import { NavLink, Outlet, Navigate } from 'react-router-dom'
import {
  LayoutDashboard, Video, Film, Search, ShieldAlert, Map,
  LogOut, Bell, FileDown, Bot, Activity, Camera, ScanFace,
} from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/lib/utils'
import { useAlertSocket } from '@/hooks/useAlertSocket'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/live', label: 'Live View', icon: Video },
  { to: '/playback', label: 'Playback', icon: Film },
  { to: '/cameras', label: 'Cameras', icon: Camera },
  { to: '/faces', label: 'Faces & Plates', icon: ScanFace },
  { to: '/events', label: 'Events', icon: Activity },
  { to: '/search', label: 'AI Search', icon: Search },
  { to: '/incidents', label: 'Incidents', icon: ShieldAlert },
  { to: '/map', label: 'Camera Map', icon: Map },
  { to: '/chat', label: 'Chat', icon: Bot },
]

export function AppShell() {
  const { token, user, logout } = useAuthStore()
  useAlertSocket()
  if (!token) return <Navigate to="/login" replace />

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-border bg-surface-2/80 backdrop-blur-md flex flex-col">
        <div className="px-4 py-5 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-accent/20 border border-accent/40 flex items-center justify-center">
              <ShieldAlert className="h-4 w-4 text-accent" />
            </div>
            <div>
              <div className="font-semibold tracking-tight text-ink leading-none">AetherShield</div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted mt-1">VMS Platform</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-accent/10 text-accent border border-accent/20'
                    : 'text-muted hover:text-ink hover:bg-surface-3',
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-border">
          <div className="text-xs text-muted mb-2 truncate">{user?.full_name}</div>
          <div className="text-[10px] uppercase tracking-wider text-accent/80 mb-3">{user?.role}</div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted hover:text-danger hover:bg-danger/10"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-border bg-surface-2/50 backdrop-blur flex items-center justify-between px-5">
          <div className="text-sm text-muted">Enterprise Video Management</div>
          <div className="flex items-center gap-3">
            <a
              href={`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/api/reports/daily.pdf`}
              onClick={(e) => {
                e.preventDefault()
                const t = useAuthStore.getState().token
                fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/api/reports/daily.pdf`, {
                  headers: { Authorization: `Bearer ${t}` },
                })
                  .then((r) => r.blob())
                  .then((b) => {
                    const url = URL.createObjectURL(b)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = 'aethershield_daily_report.pdf'
                    a.click()
                  })
              }}
              className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-accent"
            >
              <FileDown className="h-3.5 w-3.5" /> Export PDF
            </a>
            <div className="h-8 w-8 rounded-full bg-surface-3 border border-border flex items-center justify-center text-muted">
              <Bell className="h-4 w-4" />
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-5">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
