import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Camera } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { useState } from 'react'
import { toast } from 'sonner'
import { Camera as CamIcon, Usb, Wifi, Unplug, MonitorPlay } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'

type Probe = { ok: boolean; index: number; message: string; width?: number; height?: number }
type DemoStatus = { demo_count: number; enabled: boolean }

export function CamerasPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('Laptop Webcam')
  const [index, setIndex] = useState(0)
  const [remoteName, setRemoteName] = useState('Phone / IP Camera')
  const [remoteUri, setRemoteUri] = useState('')
  const [remoteType, setRemoteType] = useState<'rtsp' | 'http'>('http')
  const [remoteLocation, setRemoteLocation] = useState('Other Device')

  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ['cameras'] })
    qc.invalidateQueries({ queryKey: ['demo-status'] })
  }

  const { data: cameras = [], refetch } = useQuery({
    queryKey: ['cameras'],
    queryFn: async () =>
      (await api.get<Camera[]>('/api/cameras', { params: { include_disabled: true } })).data,
    refetchInterval: 5000,
  })

  const { data: demoStatus, refetch: refetchDemo } = useQuery({
    queryKey: ['demo-status'],
    queryFn: async () => (await api.get<DemoStatus>('/api/cameras/demo/status')).data,
  })

  const { data: probes = [], refetch: probe, isFetching: probing } = useQuery({
    queryKey: ['webcam-probe'],
    queryFn: async () => (await api.get<Probe[]>('/api/advanced/webcam/probe')).data,
    enabled: false,
  })

  const toggleDemo = useMutation({
    mutationFn: async (enabled: boolean) =>
      (await api.post('/api/cameras/demo/toggle', { enabled })).data,
    onSuccess: (data) => {
      toast.success(data.message)
      refreshAll()
    },
    onError: () => toast.error('Failed to toggle demo cameras'),
  })

  const connectWebcam = useMutation({
    mutationFn: async () =>
      (await api.post('/api/advanced/webcam/connect', null, {
        params: { index, name, location: 'This PC' },
      })).data,
    onSuccess: (data) => {
      toast.success(data.message || 'Webcam connected')
      refreshAll()
      navigate('/live')
    },
    onError: () => toast.error('Could not open webcam — close other apps using it'),
  })

  const connectRemote = useMutation({
    mutationFn: async () =>
      (await api.post('/api/cameras/connect-remote', {
        name: remoteName,
        location: remoteLocation,
        source_type: remoteType,
        source_uri: remoteUri.trim(),
        ai_enabled: true,
      })).data,
    onSuccess: (cam: Camera) => {
      toast.success(`Connected ${cam.name}`)
      setRemoteUri('')
      refreshAll()
      navigate('/live')
    },
    onError: () => toast.error('Failed to connect remote camera — check URL / network'),
  })

  const disconnect = useMutation({
    mutationFn: async (id: number) =>
      (await api.post(`/api/cameras/${id}/disconnect`, null, { params: { remove: true } })).data,
    onSuccess: (data) => {
      toast.success(data.message)
      refreshAll()
    },
    onError: () => toast.error('Disconnect failed'),
  })

  const disconnectAllLive = useMutation({
    mutationFn: async () => (await api.post('/api/cameras/disconnect-all-live')).data,
    onSuccess: (data) => {
      toast.success(data.message)
      refreshAll()
    },
    onError: () => toast.error('Failed to disconnect live cameras'),
  })

  const liveCams = cameras.filter((c) => !c.is_demo)
  const demoCams = cameras.filter((c) => c.is_demo)
  const demoOn = demoStatus?.enabled ?? demoCams.some((c) => c.enabled !== false)

  return (
    <div className="space-y-5 animate-fade-up max-w-4xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Cameras</h1>
          <p className="text-sm text-muted mt-1">
            Connect this PC, phones, or IP cameras — and turn demo feeds on/off
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={!liveCams.length || disconnectAllLive.isPending}
          onClick={() => {
            if (confirm('Disconnect and remove all live (non-demo) cameras?')) {
              disconnectAllLive.mutate()
            }
          }}
        >
          <Unplug className="h-4 w-4" /> Disconnect all live
        </Button>
      </div>

      {/* Demo toggle */}
      <div className="rounded-xl border border-border bg-panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <MonitorPlay className="h-5 w-5 text-accent mt-0.5" />
            <div>
              <h2 className="font-medium">Demo cameras</h2>
              <p className="text-xs text-muted mt-1 max-w-md">
                Sample Gate / Parking / Lobby / Warehouse feeds. Turn these <span className="text-ink">OFF</span> when
                you only want real live cameras in Live View.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => toggleDemo.mutate(!demoOn)}
            disabled={toggleDemo.isPending}
            className={cn(
              'relative h-8 w-14 rounded-full transition-colors',
              demoOn ? 'bg-accent' : 'bg-surface-3 border border-border',
            )}
            aria-label="Toggle demo cameras"
          >
            <span
              className={cn(
                'absolute top-1 h-6 w-6 rounded-full bg-white transition-all',
                demoOn ? 'left-7' : 'left-1',
              )}
            />
          </button>
        </div>
        <div className="mt-3 text-xs text-muted">
          Status: <span className={demoOn ? 'text-ok' : 'text-warn'}>{demoOn ? 'ON' : 'OFF'}</span>
          {' · '}
          {demoStatus?.demo_count ?? demoCams.length} demo camera(s)
        </div>
      </div>

      {/* Local webcam */}
      <div className="rounded-xl border border-border bg-panel p-5 space-y-4">
        <div className="flex items-center gap-2 text-accent">
          <Usb className="h-4 w-4" />
          <h2 className="font-medium text-ink">This PC webcam</h2>
        </div>
        <div className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="text-xs text-muted">Name</label>
            <input className="block h-9 rounded-md border border-border bg-surface px-3 text-sm mt-1" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-muted">Device index</label>
            <input type="number" min={0} max={9} className="block h-9 w-20 rounded-md border border-border bg-surface px-3 text-sm mt-1" value={index} onChange={(e) => setIndex(Number(e.target.value))} />
          </div>
          <Button variant="outline" onClick={() => probe()} disabled={probing}>{probing ? 'Detecting…' : 'Detect'}</Button>
          <Button onClick={() => connectWebcam.mutate()} disabled={connectWebcam.isPending}>
            <CamIcon className="h-4 w-4" /> Connect
          </Button>
        </div>
        {probes.length > 0 && (
          <div className="grid sm:grid-cols-2 gap-2">
            {probes.map((p) => (
              <button
                key={p.index}
                onClick={() => setIndex(p.index)}
                className={`text-left rounded-md border px-3 py-2 text-sm ${p.ok ? 'border-ok/40 bg-ok/5' : 'border-border text-muted'}`}
              >
                Index {p.index}: {p.message}
                {p.ok && p.width ? ` · ${p.width}×${p.height}` : ''}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Other devices */}
      <div className="rounded-xl border border-border bg-panel p-5 space-y-3">
        <div className="flex items-center gap-2 text-info">
          <Wifi className="h-4 w-4" />
          <h2 className="font-medium text-ink">Other device cameras</h2>
        </div>
        <p className="text-xs text-muted">
          Phone (Android IP Webcam / iOS RTSP apps), another PC, or CCTV NVR. Same Wi‑Fi recommended.
        </p>
        <div className="grid sm:grid-cols-2 gap-2">
          <input className="h-9 rounded-md border border-border bg-surface px-3 text-sm" placeholder="Camera name" value={remoteName} onChange={(e) => setRemoteName(e.target.value)} />
          <input className="h-9 rounded-md border border-border bg-surface px-3 text-sm" placeholder="Location" value={remoteLocation} onChange={(e) => setRemoteLocation(e.target.value)} />
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className="h-9 rounded-md border border-border bg-surface px-3 text-sm"
            value={remoteType}
            onChange={(e) => setRemoteType(e.target.value as 'rtsp' | 'http')}
          >
            <option value="http">HTTP / MJPEG (phone apps)</option>
            <option value="rtsp">RTSP (IP camera / NVR)</option>
          </select>
        </div>
        <input
          className="w-full h-9 rounded-md border border-border bg-surface px-3 text-sm font-mono"
          placeholder={
            remoteType === 'http'
              ? 'http://192.168.1.20:8080/video'
              : 'rtsp://user:pass@192.168.1.10:554/stream1'
          }
          value={remoteUri}
          onChange={(e) => setRemoteUri(e.target.value)}
        />
        <div className="text-[11px] text-muted space-y-0.5">
          <div>Android: install “IP Webcam” → Start server → use <span className="text-ink font-mono">http://PHONE_IP:8080/video</span></div>
          <div>IP CCTV: use the camera’s RTSP URL from its manual / NVR.</div>
        </div>
        <Button
          variant="outline"
          disabled={!remoteUri.trim() || connectRemote.isPending}
          onClick={() => connectRemote.mutate()}
        >
          Connect other device
        </Button>
      </div>

      {/* Camera list */}
      <div className="rounded-xl border border-border bg-panel overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-medium">All cameras</h2>
          <Button size="sm" variant="ghost" onClick={() => { refetch(); refetchDemo() }}>Refresh</Button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-border bg-surface-2">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {cameras.map((c) => (
              <tr key={c.id} className={cn('border-b border-border/50', c.enabled === false && 'opacity-50')}>
                <td className="px-4 py-2.5">
                  <div>{c.name}</div>
                  <div className="text-[10px] text-muted">{c.location}</div>
                </td>
                <td className="px-4 py-2.5">
                  <span className={cn(
                    'text-[10px] uppercase tracking-wider font-semibold',
                    c.is_demo ? 'text-muted' : 'text-accent',
                  )}>
                    {c.is_demo ? 'demo' : 'live'}
                  </span>
                  <div className="text-[10px] text-muted">{c.source_type}</div>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted max-w-[180px] truncate" title={c.source_uri}>
                  {c.source_uri}
                </td>
                <td className="px-4 py-2.5">
                  {c.enabled === false ? 'disabled' : c.status}
                </td>
                <td className="px-4 py-2.5 whitespace-nowrap">
                  <Button size="sm" variant="ghost" onClick={() => navigate(`/playback?camera=${c.id}`)}>Open</Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-danger"
                    disabled={disconnect.isPending}
                    onClick={() => {
                      const msg = c.is_demo
                        ? `Disable demo camera "${c.name}"?`
                        : `Disconnect and remove "${c.name}"?`
                      if (confirm(msg)) disconnect.mutate(c.id)
                    }}
                  >
                    {c.is_demo ? 'Disable' : 'Disconnect'}
                  </Button>
                </td>
              </tr>
            ))}
            {cameras.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted">No cameras configured</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
