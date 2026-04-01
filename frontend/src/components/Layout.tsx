import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import StatusBar from './StatusBar'

const OWNER_NAV = [
  { to: '/', label: 'Home' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/review', label: 'Review' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/config', label: 'Config' },
  { to: '/accountants', label: 'Accountants' },
]

const ACCOUNTANT_NAV = [
  { to: '/', label: 'Overview' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/export', label: 'Export' },
]

function navLinkClass({ isActive }: { isActive: boolean }): string {
  const base = 'transition-colors'
  return isActive
    ? `${base} text-blue-400 font-semibold`
    : `${base} text-gray-400 hover:text-gray-200`
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navItems = user?.role === 'accountant' ? ACCOUNTANT_NAV : OWNER_NAV

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col md:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:flex-col md:w-56 bg-gray-900 border-r border-gray-800 p-4 shrink-0">
        <h1 className="text-lg font-bold mb-6 text-white">Tax2025</h1>
        <nav className="flex flex-col gap-2 flex-1">
          {navItems.map(({ to, label }) => (
            <NavLink key={to} to={to} end={to === '/'} className={navLinkClass}>
              <div className="rounded-lg px-3 py-2 hover:bg-gray-800">{label}</div>
            </NavLink>
          ))}
        </nav>

        {/* User info + sign out */}
        {user && (
          <div className="mt-auto pt-4 border-t border-gray-800">
            <div className="flex items-center gap-2 px-2 mb-2">
              {user.picture && (
                <img
                  src={user.picture}
                  alt=""
                  className="w-7 h-7 rounded-full"
                  referrerPolicy="no-referrer"
                />
              )}
              <span className="text-xs text-gray-400 truncate">{user.name || user.email}</span>
            </div>
            <button
              onClick={logout}
              className="w-full text-left text-xs text-gray-500 hover:text-gray-300 px-3 py-1 rounded hover:bg-gray-800 transition-colors"
            >
              Sign out
            </button>
          </div>
        )}
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-h-screen">
        <StatusBar />
        <main className="flex-1 overflow-y-auto pb-20 md:pb-4">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 flex justify-around py-2 z-50">
        {navItems.map(({ to, label }) => (
          <NavLink key={to} to={to} end={to === '/'} className={navLinkClass}>
            <div className="flex flex-col items-center px-2 py-1 text-xs">{label}</div>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
