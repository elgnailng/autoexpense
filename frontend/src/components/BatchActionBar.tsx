import { useState } from 'react'

interface BatchActionBarProps {
  selectedCount: number
  role: 'owner' | 'accountant'
  categories?: string[]
  onBatchUpdate?: (category: string, deductibleStatus: string, notes: string) => void
  onBatchFlag?: (reason: string) => void
  onClear: () => void
  isPending: boolean
}

export default function BatchActionBar({ selectedCount, role, categories, onBatchUpdate, onBatchFlag, onClear, isPending }: BatchActionBarProps) {
  const [category, setCategory] = useState('')
  const [deductibleStatus, setDeductibleStatus] = useState<string>('')
  const [notes, setNotes] = useState('')
  const [flagReason, setFlagReason] = useState('')

  if (selectedCount === 0) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-800 border-t border-gray-600 p-4 z-50 shadow-lg">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-gray-300 font-medium whitespace-nowrap">
            {selectedCount} selected
          </span>

          {onBatchUpdate && (
            <>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="bg-gray-700 border border-gray-600 text-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Category...</option>
                {categories?.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>

              <select
                value={deductibleStatus}
                onChange={(e) => setDeductibleStatus(e.target.value)}
                className="bg-gray-700 border border-gray-600 text-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Status...</option>
                <option value="full">Full</option>
                <option value="partial">Partial</option>
                <option value="personal">Personal</option>
              </select>

              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Notes (optional)"
                className="bg-gray-700 border border-gray-600 text-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-40"
              />

              <button
                onClick={() => {
                  if (category && deductibleStatus) {
                    onBatchUpdate(category, deductibleStatus, notes)
                  }
                }}
                disabled={isPending || !category || !deductibleStatus}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:text-gray-400 text-white rounded px-4 py-1.5 text-sm font-medium"
              >
                {isPending ? 'Updating...' : 'Update'}
              </button>
            </>
          )}

          {role === 'accountant' && onBatchFlag && (
            <>
              <input
                type="text"
                value={flagReason}
                onChange={(e) => setFlagReason(e.target.value)}
                placeholder="Reason for flagging..."
                className="bg-gray-700 border border-gray-600 text-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 flex-1 min-w-[200px]"
              />

              <button
                onClick={() => {
                  if (flagReason.trim()) {
                    onBatchFlag(flagReason.trim())
                  }
                }}
                disabled={isPending || !flagReason.trim()}
                className="bg-yellow-600 hover:bg-yellow-500 disabled:bg-gray-600 disabled:text-gray-400 text-white rounded px-4 py-1.5 text-sm font-medium"
              >
                {isPending ? 'Flagging...' : 'Flag Selected'}
              </button>
            </>
          )}

          <button
            onClick={onClear}
            className="text-gray-400 hover:text-gray-200 text-sm ml-auto"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  )
}
