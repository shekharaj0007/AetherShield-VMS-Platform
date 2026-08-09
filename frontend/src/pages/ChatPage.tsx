import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type EventItem } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { formatTime } from '@/lib/utils'
import { Bot } from 'lucide-react'

type Msg = { role: 'user' | 'assistant'; text: string; events?: EventItem[] }

export function ChatPage() {
  const [input, setInput] = useState('What happened today?')
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: 'assistant', text: 'Ask me about detections, intrusions, or activity on any camera. Try “Summarize last 24 hours” or “Show people entering Gate A”.' },
  ])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const send = async () => {
    if (!input.trim()) return
    const userMsg = input.trim()
    setMsgs((m) => [...m, { role: 'user', text: userMsg }])
    setInput('')
    setLoading(true)
    try {
      const { data } = await api.post<{ reply: string; events: EventItem[] }>('/api/events/chat', { message: userMsg })
      setMsgs((m) => [...m, { role: 'assistant', text: data.reply, events: data.events }])
    } catch {
      setMsgs((m) => [...m, { role: 'assistant', text: 'Sorry — I could not process that request.' }])
    } finally {
      setLoading(false)
    }
  }

  const summarize = async () => {
    setLoading(true)
    try {
      const { data } = await api.get<{ summary_text: string; highlights: string[] }>('/api/events/ai/summary', { params: { hours: 24 } })
      setMsgs((m) => [
        ...m,
        { role: 'user', text: 'Summarize last 24 hours' },
        { role: 'assistant', text: `${data.summary_text}\n\nHighlights:\n${data.highlights.map((h) => `• ${h}`).join('\n')}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4 animate-fade-up">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Chat with Video</h1>
          <p className="text-sm text-muted mt-1">RAG over event metadata — ask what happened</p>
        </div>
        <Button variant="outline" size="sm" onClick={summarize} disabled={loading}>24h Summary</Button>
      </div>

      <div className="rounded-xl border border-border bg-panel h-[560px] flex flex-col">
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {msgs.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div className={
                m.role === 'user'
                  ? 'max-w-[85%] rounded-lg bg-accent/15 border border-accent/20 px-3 py-2 text-sm'
                  : 'max-w-[85%] rounded-lg bg-surface-2 border border-border px-3 py-2 text-sm whitespace-pre-wrap'
              }>
                {m.role === 'assistant' && (
                  <div className="flex items-center gap-1.5 text-accent text-xs mb-1"><Bot className="h-3.5 w-3.5" /> AetherShield AI</div>
                )}
                {m.text}
                {m.events && m.events.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {m.events.slice(0, 5).map((e) => (
                      <button
                        key={e.id}
                        onClick={() => navigate(`/playback?camera=${e.camera_id}&event=${e.id}`)}
                        className="block w-full text-left text-[11px] text-accent hover:underline"
                      >
                        → {formatTime(e.timestamp)} · {e.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="border-t border-border p-3 flex gap-2">
          <input
            className="flex-1 h-10 rounded-md border border-border bg-surface px-3 text-sm outline-none focus:border-accent/50"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="Ask about events…"
          />
          <Button onClick={send} disabled={loading}>{loading ? '…' : 'Send'}</Button>
        </div>
      </div>
    </div>
  )
}
