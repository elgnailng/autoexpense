import { useState } from 'react'
import { useStatus } from '../hooks/useApi'
import PipelineControls from '../components/PipelineControls'
import ResetPanel from '../components/ResetPanel'
import type { PipelineResult } from '../types'

interface TimestampedResult extends PipelineResult {
  timestamp: Date
}

export default function Pipeline() {
  const { data: status, isLoading } = useStatus()
  const [results, setResults] = useState<TimestampedResult[]>([])

  const handleResult = (result: PipelineResult) => {
    setResults((prev) => [{ ...result, timestamp: new Date() }, ...prev])
  }

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Pipeline</h1>

      {/* Pipeline status */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Current Status</h2>
        {isLoading ? (
          <div className="text-gray-500">Loading...</div>
        ) : status ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StageCard label="Raw" count={status.raw_count} />
            <StageCard label="Normalized" count={status.normalized_count} />
            <StageCard label="Categorized" count={status.categorized_count} />
            <StageCard label="Review Pending" count={status.review_count} accent={status.review_count > 0} />
          </div>
        ) : null}
      </div>

      {/* Controls */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Run Steps</h2>
        <PipelineControls onResult={handleResult} />
      </div>

      {/* Results log */}
      {results.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Results Log</h2>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {results.map((r, i) => {
              const hasErrors = r.stats.errors > 0
              const borderClass = !r.success
                ? 'bg-red-900/20 border-red-700 text-red-300'
                : hasErrors
                  ? 'bg-yellow-900/20 border-yellow-700 text-yellow-300'
                  : 'bg-green-900/20 border-green-700 text-green-300'
              const statusClass = !r.success
                ? 'text-red-400'
                : hasErrors
                  ? 'text-yellow-400'
                  : 'text-green-400'
              const statusLabel = !r.success
                ? 'Failed'
                : hasErrors
                  ? 'Partial'
                  : 'Success'

              return (
              <div key={i} className={`rounded-lg border p-3 text-sm ${borderClass}`}>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-medium">{r.step}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">
                      {r.timestamp.toLocaleTimeString()}
                    </span>
                    <span className={statusClass}>{statusLabel}</span>
                  </div>
                </div>
                <div className="text-gray-400">{r.message}</div>
                {hasErrors && Array.isArray(r.stats.error_messages) && r.stats.error_messages.length > 0 && (
                  <div className="mt-2 rounded bg-red-900/30 border border-red-800 p-2 text-xs text-red-300 max-h-32 overflow-y-auto space-y-1">
                    {r.stats.error_messages.map((msg: string, j: number) => (
                      <div key={j}>{msg}</div>
                    ))}
                  </div>
                )}
                {r.step === 'llm-categorize' && r.stats.total_cost_usd !== undefined && (
                  <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                    <div className="bg-gray-800 rounded px-2 py-1">
                      <span className="text-gray-500">Cost: </span>
                      <span className="text-yellow-400 font-medium">${Number(r.stats.total_cost_usd).toFixed(4)}</span>
                    </div>
                    <div className="bg-gray-800 rounded px-2 py-1">
                      <span className="text-gray-500">In: </span>
                      <span className="text-gray-300">{r.stats.total_input_tokens?.toLocaleString()}</span>
                    </div>
                    <div className="bg-gray-800 rounded px-2 py-1">
                      <span className="text-gray-500">Out: </span>
                      <span className="text-gray-300">{r.stats.total_output_tokens?.toLocaleString()}</span>
                    </div>
                  </div>
                )}
                {Object.keys(r.stats).length > 0 && (
                  <div className="mt-1 text-xs text-gray-500">
                    {Object.entries(r.stats)
                      .filter(([k]) => !['total_cost_usd', 'total_input_tokens', 'total_output_tokens', 'evaluations', 'error_messages'].includes(k))
                      .map(([k, v]) => (
                      <span key={k} className="mr-3">
                        {k}: {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Danger Zone */}
      <ResetPanel />
    </div>
  )
}

function StageCard({ label, count, accent }: { label: string; count: number; accent?: boolean }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
      <div className={`text-xl font-bold mt-1 ${accent ? 'text-yellow-400' : 'text-gray-100'}`}>
        {count}
      </div>
    </div>
  )
}
