import { useAuthStore } from '@/stores/auth'
import { streamUrl, type Camera } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Maximize2 } from 'lucide-react'

type Props = {
  camera: Camera
  onSelect?: () => void
  className?: string
}

export function LiveTile({ camera, onSelect, className }: Props) {
  const token = useAuthStore((s) => s.token) || ''
  const online = camera.status === 'online' || camera.status === 'recording'

  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-lg border border-border bg-surface-3 aspect-video cursor-pointer',
        'hover:border-accent/40 transition-colors',
        className,
      )}
      onClick={onSelect}
    >
      {online ? (
        <img
          src={streamUrl(camera.id, token)}
          alt={camera.name}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="h-full w-full flex items-center justify-center text-muted text-sm">
          Camera offline
        </div>
      )}
      <div className="absolute inset-x-0 top-0 flex items-center justify-between p-2 bg-gradient-to-b from-black/70 to-transparent">
        <div>
          <div className="text-xs font-medium text-white">{camera.name}</div>
          <div className="text-[10px] text-white/70">{camera.location}</div>
        </div>
        <div className="flex items-center gap-1.5">
          {online && (
            <span className="flex items-center gap-1 rounded bg-danger/90 px-1.5 py-0.5 text-[10px] font-semibold text-white">
              <span className="h-1.5 w-1.5 rounded-full bg-white live-dot" /> LIVE
            </span>
          )}
          <Maximize2 className="h-3.5 w-3.5 text-white/70 opacity-0 group-hover:opacity-100" />
        </div>
      </div>
      <div className="absolute bottom-2 right-2 text-[10px] font-mono text-white/80 bg-black/50 px-1.5 py-0.5 rounded">
        {camera.resolution} · {Math.round(camera.fps)} fps
      </div>
    </div>
  )
}
