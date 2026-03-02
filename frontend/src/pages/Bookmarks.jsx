import { useState, useEffect } from 'react'
import { Bookmark, Trash2 } from 'lucide-react'
import api from '../api/client'
import TenderCard from '../components/TenderCard'

export default function Bookmarks() {
  const [tenders, setTenders] = useState([])
  const [bookmarkIds, setBookmarkIds] = useState(new Set())
  const [loading, setLoading] = useState(true)

  const loadBookmarks = () => {
    setLoading(true)
    Promise.all([
      api.get('/bookmarks').then(r => setTenders(r.data)),
      api.get('/bookmarks/ids').then(r => setBookmarkIds(new Set(r.data))),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { loadBookmarks() }, [])

  const toggleBookmark = async (tenderId) => {
    try {
      await api.delete(`/bookmarks/${tenderId}`)
      setBookmarkIds(prev => { const n = new Set(prev); n.delete(tenderId); return n })
      setTenders(prev => prev.filter(t => t.id !== tenderId))
    } catch (err) { console.error(err) }
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading bookmarks...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bookmarked Tenders</h1>
        <p className="text-gray-500 mt-1">Your saved tenders for quick access ({tenders.length} saved)</p>
      </div>

      <div className="space-y-3">
        {tenders.map(t => (
          <TenderCard
            key={t.id}
            tender={t}
            bookmarked={bookmarkIds.has(t.id)}
            onToggleBookmark={toggleBookmark}
          />
        ))}
        {tenders.length === 0 && (
          <div className="text-center py-16">
            <Bookmark size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-400">No bookmarked tenders yet.</p>
            <p className="text-gray-300 text-sm mt-1">Click the bookmark icon on any tender to save it here</p>
          </div>
        )}
      </div>
    </div>
  )
}
