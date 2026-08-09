import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, type Camera } from '@/lib/api'
import { cn } from '@/lib/utils'

export function MapPage() {
  const navigate = useNavigate()
  const { data: cameras = [] } = useQuery({
    queryKey: ['cameras'],
    queryFn: async () => (await api.get<Camera[]>('/api/cameras')).data,
  })

  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Camera Map</h1>
        <p className="text-sm text-muted mt-1">Facility floor plan — click a camera to open live view</p>
      </div>

      <div className="relative aspect-[16/9] rounded-xl border border-border overflow-hidden bg-surface-3">
        {/* stylized floor plan */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <rect width="100" height="100" fill="#0f141c" />
          <rect x="5" y="8" width="90" height="84" fill="none" stroke="#2a3648" strokeWidth="0.4" />
          <rect x="8" y="12" width="35" height="30" fill="#151b25" stroke="#1e2836" strokeWidth="0.3" />
          <rect x="48" y="12" width="40" height="25" fill="#151b25" stroke="#1e2836" strokeWidth="0.3" />
          <rect x="8" y="48" width="55" height="38" fill="#151b25" stroke="#1e2836" strokeWidth="0.3" />
          <rect x="68" y="42" width="20" height="44" fill="#151b25" stroke="#1e2836" strokeWidth="0.3" />
          <text x="14" y="28" fill="#8b9bb0" fontSize="3" fontFamily="IBM Plex Sans">Lobby</text>
          <text x="55" y="26" fill="#8b9bb0" fontSize="3">Parking</text>
          <text x="25" y="68" fill="#8b9bb0" fontSize="3">Warehouse</text>
          <text x="72" y="65" fill="#8b9bb0" fontSize="3">Gate</text>
        </svg>

        {cameras.map((cam) => {
          const online = cam.status === 'online' || cam.status === 'recording'
          return (
            <button
              key={cam.id}
              title={`${cam.name} — ${cam.status}`}
              onClick={() => navigate(`/playback?camera=${cam.id}`)}
              className="absolute -translate-x-1/2 -translate-y-1/2 group"
              style={{ left: `${cam.map_x * 100}%`, top: `${cam.map_y * 100}%` }}
            >
              <span className={cn(
                'flex h-9 w-9 items-center justify-center rounded-full border-2 bg-panel shadow-lg transition-transform group-hover:scale-110',
                online ? 'border-accent text-accent' : 'border-danger text-danger',
              )}>
                <span className={cn('h-2.5 w-2.5 rounded-full', online ? 'bg-accent live-dot' : 'bg-danger')} />
              </span>
              <span className="absolute left-1/2 top-10 -translate-x-1/2 whitespace-nowrap rounded bg-black/80 px-2 py-0.5 text-[10px] opacity-0 group-hover:opacity-100">
                {cam.name}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
