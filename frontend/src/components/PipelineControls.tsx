import { useState, useCallback } from 'react'
import { useRunPipeline, useLLMProgressPoll, useStatus } from '../hooks/useApi'
import { useLLMProgress } from '../hooks/useLLMProgress'
import type { LLMRunOptions } from '../hooks/useLLMProgress'
import LLMProgressBar from './LLMProgressBar'
import LLMConfigPanel from './LLMConfigPanel'
import type { LLMConfigValues } from './LLMConfigPanel'
import type { PipelineResult, LLMProgressEvent } from '../types'

interface PipelineControlsProps {
  onResult?: (result: PipelineResult) => void
}

const ETL_STEPS = [
  { key: 'extract', label: 'Extract', description: 'Parse PDFs into raw transactions' },
  { key: 'transform', label: 'Transform', description: 'Normalize and deduplicate' },
  { key: 'categorize', label: 'Categorize', description: 'Apply rules + merchant memory' },
]

export default function PipelineControls({ onResult }: PipelineControlsProps) {
  const mutation = useRunPipeline()
  const [runningStep, setRunningStep] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const { progress, isStreaming, start: startLLM } = useLLMProgress()
  const { data: status } = useStatus()

  // LLM config state
  const [llmConfig, setLLMConfig] = useState<LLMConfigValues>({
    provider: '',
    model: '',
    apiKey: '',
  })

  const handleConfigChange = useCallback((values: LLMConfigValues) => {
    setLLMConfig(values)
  }, [])

  // Poll for LLM progress when pipeline is running but this client isn't streaming
  const shouldPoll = !!(status?.pipeline_running && !isStreaming)
  const { data: polledProgress } = useLLMProgressPoll(shouldPoll)

  // Run All LLM toggle
  const [runAllUseLLM, setRunAllUseLLM] = useState(false)

  // Recategorize toggle — clears non-memory categorizations before re-evaluating
  const [forceRecategorize, setForceRecategorize] = useState(false)

  const isRunning = runningStep !== null || isStreaming

  const handleRun = async (step: string) => {
    setRunningStep(step)
    setMessage(null)
    try {
      let options: Record<string, unknown> | undefined
      if (step === 'run') {
        options = { force: forceRecategorize }
        if (runAllUseLLM) {
          options.use_llm = true
          options.provider = llmConfig.provider || undefined
          options.model = llmConfig.model || undefined
        }
      } else if (step === 'categorize' && forceRecategorize) {
        options = { force: true }
      }
      const result = await mutation.mutateAsync({ step, options })
      setMessage(result.message)
      onResult?.(result)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setMessage(`Error: ${errorMessage}`)
    } finally {
      setRunningStep(null)
    }
  }

  const handleLLMRun = (dryRun = false) => {
    setMessage(null)
    const options: LLMRunOptions = {
      provider: llmConfig.provider || undefined,
      model: llmConfig.model || undefined,
      apiKey: llmConfig.apiKey || undefined,
      dryRun,
      force: forceRecategorize,
    }
    startLLM((result) => {
      setMessage(result.message)
      onResult?.(result)
    }, options)
  }

  // Build a progress event from polled data for the progress bar
  const polledProgressEvent: LLMProgressEvent | null =
    polledProgress?.active
      ? {
          type: polledProgress.type as LLMProgressEvent['type'] ?? 'progress',
          batch_number: polledProgress.batch_number,
          total_batches: polledProgress.total_batches,
          cumulative_categorized: polledProgress.cumulative_categorized,
          cumulative_cost_usd: polledProgress.cumulative_cost_usd,
          cumulative_input_tokens: polledProgress.cumulative_input_tokens,
          cumulative_output_tokens: polledProgress.cumulative_output_tokens,
          memory_matched: polledProgress.memory_matched,
          llm_candidates: polledProgress.llm_candidates,
          model: polledProgress.model,
        }
      : null

  const activeProgress = isStreaming ? progress : polledProgressEvent

  return (
    <div className="space-y-4">
      {/* ETL Steps */}
      <div>
        <div className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">ETL Steps</div>
        <div className="grid grid-cols-3 gap-3">
          {ETL_STEPS.map(({ key, label, description }) => (
            <button
              key={key}
              onClick={() => handleRun(key)}
              disabled={isRunning || status?.pipeline_running}
              className="rounded-lg p-3 text-left transition-colors bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:cursor-not-allowed"
            >
              <div className="font-medium text-gray-200 flex items-center gap-2">
                {runningStep === key && (
                  <span className="inline-block w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
                )}
                {label}
              </div>
              <div className="text-xs text-gray-400 mt-1">{description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* LLM Categorization */}
      <div>
        <div className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">LLM Categorization</div>
        <LLMConfigPanel onChange={handleConfigChange} disabled={isRunning || status?.pipeline_running} />
        <div className="flex gap-3 mt-3">
          <button
            onClick={() => handleLLMRun(false)}
            disabled={isRunning || status?.pipeline_running}
            className="rounded-lg px-4 py-2.5 text-sm font-medium transition-colors bg-purple-700 hover:bg-purple-600 text-white disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed"
          >
            <span className="flex items-center gap-2">
              {isStreaming && (
                <span className="inline-block w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
              )}
              LLM Categorize
            </span>
          </button>
          <button
            onClick={() => handleLLMRun(true)}
            disabled={isRunning || status?.pipeline_running}
            className="rounded-lg px-4 py-2.5 text-sm font-medium transition-colors bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed"
          >
            Dry Run
          </button>
        </div>

        {/* Progress bar (from local SSE stream or polled) */}
        {activeProgress && <div className="mt-3"><LLMProgressBar progress={activeProgress} /></div>}
      </div>

      {/* Recategorize toggle */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-3">
        <label className="flex items-start gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={forceRecategorize}
            onChange={(e) => setForceRecategorize(e.target.checked)}
            disabled={isRunning || status?.pipeline_running}
            className="w-4 h-4 mt-0.5 rounded border-gray-600 bg-gray-700 text-yellow-500 focus:ring-yellow-500 focus:ring-offset-0"
          />
          <div>
            <span className="text-sm text-gray-200">Recategorize</span>
            <p className="text-xs text-gray-400 mt-0.5">
              Clear existing non-memory categorizations and re-evaluate with current rules. Merchant memory decisions are always preserved.
            </p>
          </div>
        </label>
      </div>

      {/* Export */}
      <div>
        <div className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Export</div>
        <button
          onClick={() => handleRun('export')}
          disabled={isRunning || status?.pipeline_running}
          className="rounded-lg px-4 py-2.5 text-sm font-medium transition-colors bg-gray-700 hover:bg-gray-600 text-gray-200 disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed"
        >
          <span className="flex items-center gap-2">
            {runningStep === 'export' && (
              <span className="inline-block w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
            )}
            Export CSVs
          </span>
        </button>
      </div>

      {/* Run All */}
      <div className="border-t border-gray-700 pt-4">
        <div className="flex items-center justify-between mb-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={runAllUseLLM}
              onChange={(e) => setRunAllUseLLM(e.target.checked)}
              disabled={isRunning || status?.pipeline_running}
              className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-purple-500 focus:ring-purple-500 focus:ring-offset-0"
            />
            <span className="text-sm text-gray-300">Use LLM categorization</span>
          </label>
        </div>
        <button
          onClick={() => handleRun('run')}
          disabled={isRunning || status?.pipeline_running}
          className={`w-full rounded-lg p-3 text-left transition-colors disabled:cursor-not-allowed ${
            runAllUseLLM
              ? 'bg-purple-700 hover:bg-purple-600 disabled:bg-purple-900'
              : 'bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900'
          }`}
        >
          <div className="font-medium text-white flex items-center gap-2">
            {runningStep === 'run' && (
              <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            Run All
          </div>
          <div className={`text-xs mt-1 ${runAllUseLLM ? 'text-purple-200' : 'text-blue-200'}`}>
            Extract &rarr; Transform &rarr; {runAllUseLLM ? 'LLM Categorize' : 'Categorize'} &rarr; Export
          </div>
        </button>
      </div>

      {/* Status message */}
      {message && !isStreaming && (
        <div
          className={`rounded-lg p-3 text-sm ${
            message.startsWith('Error')
              ? 'bg-red-900/30 border border-red-700 text-red-300'
              : 'bg-green-900/30 border border-green-700 text-green-300'
          }`}
        >
          {message}
        </div>
      )}
    </div>
  )
}
