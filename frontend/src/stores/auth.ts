import { create } from 'zustand'
import { login as apiLogin, refreshToken as apiRefreshToken } from '@/api/auth'
import { getUserFromToken } from '@/utils/auth'

export interface UserInfo {
  id: string
  username: string
  role: 'admin' | 'user'
}

interface AuthState {
  token: string | null
  isAuthenticated: boolean
  user: UserInfo | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<void>
}

function loadUser(): UserInfo | null {
  const token = localStorage.getItem('token')
  if (!token) return null
  return getUserFromToken(token)
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  user: loadUser(),

  login: async (username: string, password: string) => {
    const data = await apiLogin({ username, password })
    localStorage.setItem('token', data.access_token)
    set({
      token: data.access_token,
      isAuthenticated: true,
      user: getUserFromToken(data.access_token),
    })
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, isAuthenticated: false, user: null })
    window.location.href = '/login'
  },

  refreshToken: async () => {
    try {
      const data = await apiRefreshToken()
      localStorage.setItem('token', data.access_token)
      set({
        token: data.access_token,
        user: getUserFromToken(data.access_token),
      })
    } catch {
      localStorage.removeItem('token')
      set({ token: null, isAuthenticated: false, user: null })
    }
  },
}))
