import { useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void
          renderButton: (element: HTMLElement, config: Record<string, unknown>) => void
        }
      }
    }
  }
}

export default function Login() {
  const { user, loading, login, error } = useAuth()
  const buttonRef = useRef<HTMLDivElement>(null)
  const [clientId, setClientId] = useState<string | null>(null)
  const [gisReady, setGisReady] = useState(false)

  // Fetch the Google Client ID from the backend
  useEffect(() => {
    fetch('/api/auth/client-id')
      .then(res => res.json())
      .then(data => {
        if (data.client_id) setClientId(data.client_id)
      })
      .catch(() => {})
  }, [])

  // Wait for GIS script to load
  useEffect(() => {
    if (window.google?.accounts?.id) {
      setGisReady(true)
      return
    }

    const check = setInterval(() => {
      if (window.google?.accounts?.id) {
        setGisReady(true)
        clearInterval(check)
      }
    }, 100)

    return () => clearInterval(check)
  }, [])

  // Initialize the Google button once both clientId and GIS are ready
  useEffect(() => {
    if (!clientId || !gisReady || !buttonRef.current) return

    window.google!.accounts.id.initialize({
      client_id: clientId,
      callback: (response: { credential: string }) => {
        login(response.credential)
      },
    })

    window.google!.accounts.id.renderButton(buttonRef.current, {
      theme: 'filled_black',
      size: 'large',
      width: 300,
      text: 'signin_with',
    })
  }, [clientId, gisReady, login])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    )
  }

  if (user) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 max-w-sm w-full mx-4 text-center">
        <h1 className="text-2xl font-bold text-white mb-2">Tax2025</h1>
        <p className="text-gray-400 text-sm mb-8">Expense Tracker</p>

        {!clientId ? (
          <p className="text-yellow-400 text-sm">
            Google Client ID not configured. Set GOOGLE_CLIENT_ID env var.
          </p>
        ) : (
          <div className="flex justify-center">
            <div ref={buttonRef} />
          </div>
        )}

        {error && (
          <p className="mt-4 text-red-400 text-sm">{error}</p>
        )}
      </div>
    </div>
  )
}
