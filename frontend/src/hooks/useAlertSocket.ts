import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'

const WS_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/^http/, 'ws') + '/ws/alerts'

export function useAlertSocket() {
  const token = useAuthStore((s) => s.token)
  const navigate = useNavigate()
  const navRef = useRef(navigate)
  navRef.current = navigate

  useEffect(() => {
    if (!token) return
    let ws: WebSocket | null = null
    let closed = false
    let ping: number | undefined

    const connect = () => {
      if (closed) return
      ws = new WebSocket(WS_URL)
      ws.onopen = () => {
        ping = window.setInterval(() => {
          try { ws?.send('ping') } catch { /* ignore */ }
        }, 25000)
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type !== 'alert') return
          const title = msg.title || 'Security alert'
          const isCrit = msg.priority === 'critical'
          toast[isCrit ? 'error' : 'warning'](title, {
            description: `${msg.event_type || 'event'} · Camera ${msg.camera_id}`,
            action: msg.event_id ? {
              label: 'Open',
              onClick: () => navRef.current(`/playback?camera=${msg.camera_id}&event=${msg.event_id}`),
            } : undefined,
            duration: 8000,
          })
          if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification('AetherShield', { body: title })
          }
        } catch { /* ignore */ }
      }
      ws.onclose = () => {
        if (ping) clearInterval(ping)
        if (!closed) setTimeout(connect, 3000)
      }
    }

    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {})
    }
    connect()
    return () => {
      closed = true
      if (ping) clearInterval(ping)
      ws?.close()
    }
  }, [token])
}
