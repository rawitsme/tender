import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import TenderSearch from './pages/TenderSearch'
import TenderDetail from './pages/TenderDetail'
import Compare from './pages/Compare'
import Alerts from './pages/Alerts'
import Browse from './pages/Browse'
import Bookmarks from './pages/Bookmarks'
import Login from './pages/Login'
import Admin from './pages/Admin'
import DownloadCenter from './pages/DownloadCenter'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>
  return user ? children : <Navigate to="/login" />
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="search" element={<TenderSearch />} />
          <Route path="tenders/:id" element={<TenderDetail />} />
          <Route path="compare" element={<Compare />} />
          <Route path="browse" element={<Browse />} />
          <Route path="bookmarks" element={<Bookmarks />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="admin" element={<Admin />} />
          <Route path="download" element={<DownloadCenter />} />
          {/* SEO-friendly routes */}
          <Route path="tenders/category/:keyword" element={<TenderSearch />} />
          <Route path="tenders/state/:state" element={<TenderSearch />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
