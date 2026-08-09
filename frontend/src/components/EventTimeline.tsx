import { EVENT_COLORS, PRIORITY_COLOR, formatTime, cn } from '@/lib/utils'
import type { EventItem } from '@/lib/api'

type Props = {
  events: EventItem[]
  start?: Date
  end?: Date
  onSelect?: (event: EventItem) => void
  selectedId?: number | null
}

export function EventTimeline({ events, start, end, onSelect, selectedId }: Props) {
  const s = start ?? new Date(Date.now() - 24 * 3600 * 1000)
  const e = end ?? new Date()
  const span = Math.max(e.getTime() - s.getTime(), 1)

  return (
    <div className="space-y-2">
      <div className="relative h-14 rounded-md border border-border bg-surface-3 overflow-hidden">
        <div className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: 'repeating-linear-gradient(90deg, transparent, transparent 49px, #2a3648 50px)',
          }}
        />
        {events.map((ev) => {
          const t = new Date(ev.timestamp).getTime()
          const left = ((t - s.getTime()) / span) * 100
          if (left < 0 || left > 100) return null
          const color = EVENT_COLORS[ev.event_type] || PRIORITY_COLOR[ev.priority] || '#22c55e'
          return (
            <button
              key={ev.id}
              title={`${formatTime(ev.timestamp)}\n${ev.label}\nConfidence ${(ev.confidence * 100).toFixed(0)}%\n${ev.camera_name || ''}`}
              onClick={() => onSelect?.(ev)}
              className={cn(
                'absolute top-1/2 -translate-y-1/2 h-3 w-3 rounded-full border-2 border-surface-3 transition-transform hover:scale-150',
                selectedId === ev.id && 'ring-2 ring-accent scale-150',
              )}
              style={{ left: `${left}%`, backgroundColor: color }}
            />
          )
        })}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-muted">
        <span>{s.toLocaleTimeString()}</span>
        <span>AI Event Timeline</span>
        <span>{e.toLocaleTimeString()}</span>
      </div>
      <div className="flex flex-wrap gap-3 text-[10px] text-muted">
        {Object.entries(EVENT_COLORS).slice(0, 6).map(([k, c]) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ background: c }} /> {k}
          </span>
        ))}
      </div>
    </div>
  )
}
