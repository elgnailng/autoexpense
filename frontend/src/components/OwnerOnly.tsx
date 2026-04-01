import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function OwnerOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  if (user?.role !== 'owner') return <Navigate to="/" replace />
  return <>{children}</>
}
