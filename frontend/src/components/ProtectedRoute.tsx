import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'

/** admin 专属路由前缀 */
const adminPaths = ['/gateway', '/users', '/audit', '/usage', '/api-keys']

interface ProtectedRouteProps {
  children: React.ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const user = useAuthStore((state) => state.user)
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // 非 admin 访问 admin 页面时重定向
  const role = user?.role || 'user'
  if (role !== 'admin' && adminPaths.some((p) => location.pathname.startsWith(p))) {
    return <Navigate to="/chat" replace />
  }

  return <>{children}</>
}
