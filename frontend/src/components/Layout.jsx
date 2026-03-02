import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { LayoutDashboard, Search, Bell, Shield, LogOut, Compass, Bookmark } from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/search', icon: Search, label: 'Search Tenders' },
  { to: '/browse', icon: Compass, label: 'Browse' },
  { to: '/bookmarks', icon: Bookmark, label: 'Bookmarks' },
  { to: '/alerts', icon: Bell, label: 'Alerts' },
  { to: '/admin', icon: Shield, label: 'Admin' },
]

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-primary-900 text-white flex flex-col">
        <div className="p-6 border-b border-white/10">
          <h1 className="text-xl font-bold">🏛️ TenderWatch</h1>
          <p className="text-sm text-white/60 mt-1">Government Tender Aggregator</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive ? 'bg-white/15 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-white/10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{user?.full_name || user?.email}</p>
              <p className="text-xs text-white/50">{user?.role}</p>
            </div>
            <button onClick={logout} className="p-2 hover:bg-white/10 rounded-lg" title="Logout">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
