import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { LayoutDashboard, Search, Bell, Shield, LogOut, Compass, Bookmark, Menu, X, GitCompare, Download } from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/search', icon: Search, label: 'Search Tenders' },
  { to: '/browse', icon: Compass, label: 'Browse' },
  { to: '/download', icon: Download, label: 'Download Center' },
  { to: '/bookmarks', icon: Bookmark, label: 'Bookmarks' },
  { to: '/alerts', icon: Bell, label: 'Alerts' },
  { to: '/admin', icon: Shield, label: 'Admin' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const sidebar = (
    <>
      <div className="p-6 border-b border-white/10">
        <h1 className="text-xl font-bold">🏛️ TenderWatch</h1>
        <p className="text-sm text-white/60 mt-1">Government Tender Aggregator</p>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'} onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors ${
                isActive ? 'bg-white/15 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'
              }`
            }>
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-white/10">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{user?.full_name || user?.email}</p>
            <p className="text-xs text-white/50">{user?.role}</p>
          </div>
          <button onClick={logout} className="p-2 hover:bg-white/10 rounded-lg shrink-0" title="Logout">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </>
  )

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-64 bg-primary-900 text-white flex-col shrink-0">
        {sidebar}
      </aside>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-64 h-full bg-primary-900 text-white flex flex-col">
            <button onClick={() => setSidebarOpen(false)}
              className="absolute top-4 right-4 p-1 text-white/70 hover:text-white">
              <X size={20} />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-auto min-w-0">
        {/* Mobile header */}
        <div className="md:hidden flex items-center gap-3 p-4 bg-white border-b sticky top-0 z-40">
          <button onClick={() => setSidebarOpen(true)} className="p-1">
            <Menu size={22} />
          </button>
          <h1 className="font-bold text-gray-900">🏛️ TenderWatch</h1>
        </div>
        <div className="p-4 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
