import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/Button'

export function LoginPage() {
  const { token, login } = useAuthStore()
  const [email, setEmail] = useState('admin@aethershield.io')
  const [password, setPassword] = useState('admin123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (token) return <Navigate to="/" replace />

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(email, password)
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(30,40,54,0.35)_1px,transparent_1px),linear-gradient(90deg,rgba(30,40,54,0.35)_1px,transparent_1px)] bg-[size:48px_48px]" />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-surface/40 to-surface" />

      <form
        onSubmit={onSubmit}
        className="relative w-full max-w-md animate-fade-up rounded-xl border border-border bg-panel/90 backdrop-blur-xl p-8 shadow-2xl"
      >
        <div className="flex items-center gap-3 mb-8">
          <div className="h-11 w-11 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center">
            <ShieldAlert className="h-5 w-5 text-accent" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">AetherShield</h1>
            <p className="text-xs text-muted tracking-[0.16em] uppercase mt-0.5">Video Management System</p>
          </div>
        </div>

        <label className="block text-xs text-muted mb-1.5">Email</label>
        <input
          className="w-full mb-4 h-10 rounded-md border border-border bg-surface px-3 text-sm outline-none focus:border-accent/50"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <label className="block text-xs text-muted mb-1.5">Password</label>
        <input
          type="password"
          className="w-full mb-5 h-10 rounded-md border border-border bg-surface px-3 text-sm outline-none focus:border-accent/50"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm text-danger mb-3">{error}</p>}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </Button>
        <p className="mt-5 text-[11px] text-muted leading-relaxed">
          Demo: admin@aethershield.io / admin123 · operator@aethershield.io / operator123 · viewer@aethershield.io / viewer123
        </p>
      </form>
    </div>
  )
}
