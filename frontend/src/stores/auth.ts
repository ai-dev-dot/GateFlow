import { create } from 'zustand'
import { login as apiLogin, refreshToken as apiRefreshToken } from '@/api/auth'

interface AuthState {
  token: string | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),

  login: async (username: string, password: string) => {
    const data = await apiLogin({ username, password })
    localStorage.setItem('token', data.access_token)
    set({ token: data.access_token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, isAuthenticated: false })
    window.location.href = '/login'
  },

  refreshToken: async () => {
    try {
      const data = await apiRefreshToken()
      localStorage.setItem('token', data.access_token)
      set({ token: data.access_token })
    } catch {
      localStorage.removeItem('token')
      set({ token: null, isAuthenticated: false })
    }
  },
}))
