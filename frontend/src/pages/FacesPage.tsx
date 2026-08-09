import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { useState } from 'react'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { formatTime } from '@/lib/utils'

type Face = { name: string; category: string; path: string }

export function FacesPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [category, setCategory] = useState('known')
  const [file, setFile] = useState<File | null>(null)
  const [plateQ, setPlateQ] = useState('DL 10')

  const { data: faces = [] } = useQuery({
    queryKey: ['faces'],
    queryFn: async () => (await api.get<Face[]>('/api/advanced/faces')).data,
  })

  const enroll = async () => {
    if (!file || !name) {
      toast.error('Name and photo required')
      return
    }
    const fd = new FormData()
    fd.append('name', name)
    fd.append('category', category)
    fd.append('file', file)
    await api.post('/api/advanced/faces', fd)
    toast.success(`Enrolled ${name}`)
    setName('')
    setFile(null)
    qc.invalidateQueries({ queryKey: ['faces'] })
  }

  const searchPlates = useQuery({
    queryKey: ['plates', plateQ],
    queryFn: async () => (await api.get('/api/advanced/plates/search', { params: { q: plateQ } })).data,
    enabled: false,
  })

  return (
    <div className="space-y-5 animate-fade-up max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Faces & Plates</h1>
        <p className="text-sm text-muted mt-1">Enroll known / blacklist faces · search license plates</p>
      </div>

      <div className="rounded-xl border border-border bg-panel p-5 space-y-3">
        <h2 className="text-sm font-medium">Enroll face</h2>
        <div className="flex flex-wrap gap-2 items-end">
          <input className="h-9 rounded-md border border-border bg-surface px-3 text-sm" placeholder="Name (e.g. Raj)" value={name} onChange={(e) => setName(e.target.value)} />
          <select className="h-9 rounded-md border border-border bg-surface px-3 text-sm" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="known">Known / Employee</option>
            <option value="blacklist">Blacklist</option>
          </select>
          <input type="file" accept="image/*" className="text-xs text-muted" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <Button onClick={enroll}>Enroll</Button>
        </div>
        <p className="text-[11px] text-muted">Tip: use a clear frontal face photo. Blacklist matches raise critical alerts.</p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {faces.map((f) => (
          <div key={f.name} className="rounded-xl border border-border bg-panel p-4">
            <div className="font-medium">{f.name}</div>
            <div className={`text-xs mt-1 uppercase tracking-wider ${f.category === 'blacklist' ? 'text-danger' : f.category === 'known' ? 'text-ok' : 'text-warn'}`}>
              {f.category}
            </div>
            <Button
              size="sm"
              variant="ghost"
              className="mt-2"
              onClick={async () => {
                await api.delete(`/api/advanced/faces/${encodeURIComponent(f.name)}`)
                qc.invalidateQueries({ queryKey: ['faces'] })
              }}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-border bg-panel p-5 space-y-3">
        <h2 className="text-sm font-medium">License plate search</h2>
        <div className="flex gap-2">
          <input className="flex-1 h-9 rounded-md border border-border bg-surface px-3 text-sm font-mono" value={plateQ} onChange={(e) => setPlateQ(e.target.value)} placeholder="DL 10 AB 2424" />
          <Button onClick={() => searchPlates.refetch()}>Search</Button>
        </div>
        <div className="space-y-2">
          {(searchPlates.data || []).map((p: { id: number; camera_id: number; label: string; plate: string; timestamp: string }) => (
            <button
              key={p.id}
              className="w-full text-left rounded-md border border-border px-3 py-2 text-sm hover:border-accent/40"
              onClick={() => navigate(`/playback?camera=${p.camera_id}&event=${p.id}`)}
            >
              <span className="font-mono text-accent">{p.plate || p.label}</span>
              <span className="text-xs text-muted ml-2">{formatTime(p.timestamp)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
