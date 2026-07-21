import { Navigate, Outlet } from 'react-router-dom'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { useAuth } from '@/context/AuthContext'

export function RequireAuth() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <LoadingSpinner label="Chargement…" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
