import { useState } from 'react'
import { useResetPipeline } from '../hooks/useApi'

const LEVELS = [
  {
    value: 'soft',
    label: 'Soft',
    description: 'Database, output CSVs, logs. Keeps merchant memory, config, and rules.',
  },
  {
    value: 'medium',
    label: 'Medium',
    description: 'Soft + merchant memory + config history. Keeps rules and deduction rules.',
  },
  {
    value: 'hard',
    label: 'Hard',
    description: 'Everything. Full factory reset (all config files backed up first).',
  },
] as const

export default function ResetPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [level, setLevel] = useState<string>('soft')
  const [confirming, setConfirming] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const mutation = useResetPipeline()

  const handleReset = async () => {
    setConfirming(false)
    setResult(null)
    try {
      const res = await mutation.mutateAsync(level)
      setResult(res.message)
    } catch (err) {
      setResult(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800 hover:bg-gray-750 text-left"
      >
        <span className="text-sm font-medium text-red-400">Danger Zone</span>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="bg-gray-900 border-t border-gray-700 p-4 space-y-4">
          <div className="text-sm text-gray-400">
            Reset pipeline data. Config files are always backed up before deletion.
          </div>

          {/* Level selection */}
          <div className="space-y-2">
            {LEVELS.map((l) => (
              <label
                key={l.value}
                className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                  level === l.value
                    ? 'border-red-600 bg-red-900/10'
                    : 'border-gray-700 hover:border-gray-600'
                }`}
              >
                <input
                  type="radio"
                  name="reset-level"
                  value={l.value}
                  checked={level === l.value}
                  onChange={() => setLevel(l.value)}
                  className="mt-0.5 accent-red-500"
                />
                <div>
                  <div className="text-sm font-medium text-gray-200">{l.label}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{l.description}</div>
                </div>
              </label>
            ))}
          </div>

          {/* Confirm / Reset button */}
          {!confirming ? (
            <button
              onClick={() => setConfirming(true)}
              disabled={mutation.isPending}
              className="px-4 py-2 bg-red-700 hover:bg-red-600 text-white text-sm font-medium rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Reset Pipeline
            </button>
          ) : (
            <div className="flex items-center gap-3">
              <span className="text-sm text-red-400">Are you sure?</span>
              <button
                onClick={handleReset}
                disabled={mutation.isPending}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded disabled:opacity-50"
              >
                {mutation.isPending ? 'Resetting...' : 'Confirm Reset'}
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded"
              >
                Cancel
              </button>
            </div>
          )}

          {/* Result */}
          {result && (
            <div
              className={`rounded-lg p-3 text-sm ${
                result.startsWith('Error')
                  ? 'bg-red-900/30 border border-red-700 text-red-300'
                  : 'bg-green-900/30 border border-green-700 text-green-300'
              }`}
            >
              {result}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
