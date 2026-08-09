import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

type User = {
  id: number
  email: string
  full_name: string
  role: string
  is_active: boolean
}

type AuthState = {
  token: string | null
  user: User | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      login: async (email, password) => {
        const { data } = await axios.post(`${API_BASE}/api/auth/login/json`, { email, password })
        set({ token: data.access_token })
        await get().fetchMe()
      },
      logout: () => set({ token: null, user: null }),
      fetchMe: async () => {
        const token = get().token
        if (!token) return
        const { data } = await axios.get(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        set({ user: data })
      },
    }),
    { name: 'aethershield-auth' },
  ),
)
