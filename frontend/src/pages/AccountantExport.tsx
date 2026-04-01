import { useState } from 'react'
import { api } from '../api/client'

const EXPORT_FILES = [
  { type: 'business_expenses', label: 'Business Expenses', description: 'Deductible transactions (full + partial)' },
  { type: 'all_transactions', label: 'All Transactions', description: 'Every transaction across all institutions' },
  { type: 'category_summary', label: 'Category Summary', description: 'Totals grouped by CRA expense category' },
  { type: 'review_required', label: 'Review Required', description: 'Transactions flagged for review' },
]

export default function AccountantExport() {
  const [downloading, setDownloading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleDownload = async (fileType: string) => {
    setDownloading(fileType)
    setError(null)
    try {
      await api.downloadExport(fileType)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="p-4 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Export Data</h1>
      <p className="text-gray-400 text-sm mb-6">Download expense data as CSV files for your records.</p>

      {error && (
        <div className="mb-4 rounded-lg p-3 bg-red-900/30 border border-red-700 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {EXPORT_FILES.map(({ type, label, description }) => (
          <div
            key={type}
            className="bg-gray-800 rounded-lg p-4 border border-gray-700 flex items-center justify-between"
          >
            <div>
              <div className="font-medium text-gray-200">{label}</div>
              <div className="text-sm text-gray-400">{description}</div>
            </div>
            <button
              onClick={() => handleDownload(type)}
              disabled={downloading !== null}
              className="shrink-0 ml-4 rounded-lg px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:bg-blue-900 disabled:text-blue-400 transition-colors"
            >
              {downloading === type ? 'Downloading...' : 'Download'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
