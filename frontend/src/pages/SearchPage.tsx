import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type EventItem } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { formatTime, PRIORITY_COLOR } from '@/lib/utils'
import { Search } from 'lucide-react'

const SUGGESTIONS = [
  'Show all people today',
  'Find intrusions',
  'Vehicles yesterday',
  'Critical events last 24 hours',
  'Find people after 9 PM',
  'Show motion on camera 1',
]

export function SearchPage() {
  const [query, setQuery] = useState('Show all people today')
  const [results, setResults] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const run = async (q = query) => {
    setLoading(true)
    try {
      const { data } = await api.post<EventItem[]>('/api/events/search', { query: q, limit: 50 })
      setResults(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5 animate-fade-up max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">AI Search</h1>
        <p className="text-sm text-muted mt-1">Natural language search over detection events</p>
      </div>

      <div className="rounded-xl border border-border bg-panel p-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <input
              className="w-full h-11 rounded-md border border-border bg-surface pl-10 pr-3 text-sm outline-none focus:border-accent/50"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && run()}
              placeholder='e.g. "Show all red cars yesterday"'
            />
          </div>
          <Button onClick={() => run()} disabled={loading}>{loading ? 'Searching…' : 'Search'}</Button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => { setQuery(s); run(s) }}
              className="text-[11px] rounded-full border border-border px-3 py-1 text-muted hover:text-accent hover:border-accent/40"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-xs text-muted">{results.length} result(s)</div>
        {results.map((e) => (
          <button
            key={e.id}
            onClick={() => navigate(`/playback?camera=${e.camera_id}&event=${e.id}`)}
            className="w-full text-left rounded-xl border border-border bg-panel px-4 py-3 hover:border-accent/40 transition-colors"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="font-medium">{e.label}</div>
              <span className="text-xs uppercase" style={{ color: PRIORITY_COLOR[e.priority] }}>{e.priority}</span>
            </div>
            <div className="text-xs text-muted mt-1">
              {e.camera_name} · {formatTime(e.timestamp)} · {(e.confidence * 100).toFixed(0)}% confidence
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
