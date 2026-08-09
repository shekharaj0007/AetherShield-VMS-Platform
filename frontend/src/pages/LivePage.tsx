import { useQuery } from '@tanstack/react-query'
import { api, type Camera } from '@/lib/api'
import { LiveTile } from '@/components/LiveTile'
import { useAppStore } from '@/stores/app'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'

const GRIDS: Array<1 | 2 | 4 | 9 | 16> = [1, 2, 4, 9, 16]

export function LivePage() {
  const { gridSize, setGridSize, setSelectedCameraId } = useAppStore()
  const navigate = useNavigate()
  const { data: cameras = [] } = useQuery({
    queryKey: ['cameras'],
    queryFn: async () => (await api.get<Camera[]>('/api/cameras')).data,
    refetchInterval: 8000,
  })

  const cols =
    gridSize === 1 ? 'grid-cols-1' :
    gridSize === 2 ? 'grid-cols-1 md:grid-cols-2' :
    gridSize === 4 ? 'grid-cols-1 md:grid-cols-2' :
    gridSize === 9 ? 'grid-cols-2 md:grid-cols-3' :
    'grid-cols-2 md:grid-cols-4'

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Live View</h1>
          <p className="text-sm text-muted mt-1">Multi-camera monitoring with AI overlays</p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-panel p-1">
          {GRIDS.map((n) => (
            <button
              key={n}
              onClick={() => setGridSize(n)}
              className={cn(
                'h-8 min-w-8 px-2 rounded-md text-xs font-medium transition-colors',
                gridSize === n ? 'bg-accent text-surface' : 'text-muted hover:text-ink',
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <div className={cn('grid gap-3', cols)}>
        {cameras.slice(0, gridSize).map((cam) => (
          <LiveTile
            key={cam.id}
            camera={cam}
            onSelect={() => {
              setSelectedCameraId(cam.id)
              navigate(`/playback?camera=${cam.id}`)
            }}
          />
        ))}
      </div>

      {cameras.length === 0 && (
        <div className="rounded-xl border border-dashed border-border p-10 text-center text-muted">
          No cameras configured. Seed data will create demo cameras on backend start.
          <div className="mt-3">
            <Button onClick={() => window.location.reload()}>Refresh</Button>
          </div>
        </div>
      )}
    </div>
  )
}
