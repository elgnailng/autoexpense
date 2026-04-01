import type { LLMProgressEvent } from '../types'

interface LLMProgressBarProps {
  progress: LLMProgressEvent
}

export default function LLMProgressBar({ progress }: LLMProgressBarProps) {
  if (progress.type === 'error') {
    return (
      <div className="rounded-lg border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">
        <span className="font-medium">Error: </span>
        {progress.message}
      </div>
    )
  }

  if (progress.type === 'start') {
    return (
      <div className="rounded-lg border border-blue-700 bg-blue-900/20 p-3 text-sm text-blue-300">
        <div className="font-medium mb-1">Starting LLM categorization...</div>
        <div className="text-xs text-gray-400 space-x-3">
          <span>{progress.memory_matched} matched from memory</span>
          <span>{progress.llm_candidates} to evaluate via LLM</span>
          <span>{progress.total_batches} batches</span>
          {progress.model && <span className="font-mono">{progress.model}</span>}
        </div>
      </div>
    )
  }

  if (progress.type === 'progress') {
    const pct =
      progress.total_batches && progress.total_batches > 0
        ? Math.round(((progress.batch_number || 0) / progress.total_batches) * 100)
        : 0

    return (
      <div className="rounded-lg border border-blue-700 bg-blue-900/20 p-3 text-sm">
        {/* Progress bar */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-blue-300 font-medium">
            Batch {progress.batch_number}/{progress.total_batches}
          </span>
          <span className="text-gray-400 text-xs">{pct}%</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
          <div
            className="bg-blue-500 h-2 rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="bg-gray-800 rounded px-2 py-1">
            <span className="text-gray-500">Categorized: </span>
            <span className="text-gray-200">{progress.cumulative_categorized}</span>
          </div>
          <div className="bg-gray-800 rounded px-2 py-1">
            <span className="text-gray-500">Cost: </span>
            <span className="text-yellow-400 font-medium">
              ${(progress.cumulative_cost_usd || 0).toFixed(4)}
            </span>
          </div>
          <div className="bg-gray-800 rounded px-2 py-1">
            <span className="text-gray-500">Tokens: </span>
            <span className="text-gray-300">
              {((progress.cumulative_input_tokens || 0) + (progress.cumulative_output_tokens || 0)).toLocaleString()}
            </span>
          </div>
        </div>
      </div>
    )
  }

  if (progress.type === 'complete') {
    return (
      <div className="rounded-lg border border-green-700 bg-green-900/20 p-3 text-sm text-green-300">
        <span className="font-medium">Complete: </span>
        {progress.message}
      </div>
    )
  }

  return null
}
