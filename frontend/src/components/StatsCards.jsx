import { FileText, Clock, TrendingUp, Database } from 'lucide-react'

export default function StatsCards({ stats }) {
  if (!stats) return null

  const cards = [
    { label: 'Total Tenders', value: stats.total_tenders?.toLocaleString(), icon: Database, color: 'text-blue-600 bg-blue-50' },
    { label: 'Active Tenders', value: stats.active_tenders?.toLocaleString(), icon: FileText, color: 'text-green-600 bg-green-50' },
    { label: 'Closing This Week', value: stats.tenders_closing_this_week?.toLocaleString(), icon: Clock, color: 'text-orange-600 bg-orange-50' },
    { label: 'Avg Value', value: stats.avg_tender_value ? `₹${(stats.avg_tender_value / 100000).toFixed(1)}L` : '—', icon: TrendingUp, color: 'text-purple-600 bg-purple-50' },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(({ label, value, icon: Icon, color }) => (
        <div key={label} className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-lg ${color}`}><Icon size={20} /></div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{value}</p>
              <p className="text-sm text-gray-500">{label}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
