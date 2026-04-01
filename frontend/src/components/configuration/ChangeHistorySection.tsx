import { useState } from 'react'
import { useConfigHistory } from '../../hooks/useApi'
import { ACTION_STYLES } from './utils'

export default function ChangeHistorySection() {
  const [filter, setFilter] = useState<string>('')
  const { data: history, isLoading } = useConfigHistory(100, filter || undefined)

  if (isLoading) return <div className="text-gray-500">Loading history...</div>

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <select
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All files</option>
          <option value="rules.yaml">rules.yaml</option>
          <option value="deduction_rules.yaml">deduction_rules.yaml</option>
        </select>
        <span className="text-sm text-gray-500">{history?.length ?? 0} entries</span>
      </div>

      {!history?.length ? (
        <div className="text-gray-500 text-sm">No config changes recorded yet.</div>
      ) : (
        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {history.map((entry, index) => {
            const style = ACTION_STYLES[entry.action] ?? 'bg-gray-800 text-gray-300 border-gray-700'
            const timestamp = entry.timestamp.slice(0, 19).replace('T', ' ')

            return (
              <div key={index} className={`rounded-lg border p-3 ${style}`}>
                <div className="flex justify-between items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-semibold uppercase tracking-wide">
                      {entry.action}
                    </span>
                    <span className="text-xs text-gray-400 ml-2 font-mono">{entry.config_file}</span>
                    <div className="text-sm mt-1 text-gray-200">{entry.detail}</div>
                  </div>
                  <div className="text-xs text-gray-500 shrink-0 text-right">
                    <div>{timestamp} UTC</div>
                    <div>{entry.source}</div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
