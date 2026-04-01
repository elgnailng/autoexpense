import { useState, useEffect } from 'react'
import { useLLMConfig } from '../hooks/useApi'

export interface LLMConfigValues {
  provider: string
  model: string
  apiKey: string
}

interface LLMConfigPanelProps {
  onChange: (values: LLMConfigValues) => void
  disabled?: boolean
}

export default function LLMConfigPanel({ onChange, disabled }: LLMConfigPanelProps) {
  const { data: config, isLoading } = useLLMConfig()

  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')

  // Initialize from server config
  useEffect(() => {
    if (config && !provider) {
      setProvider(config.provider)
      setModel(config.model)
    }
  }, [config, provider])

  // Notify parent on change
  useEffect(() => {
    onChange({ provider, model, apiKey })
  }, [provider, model, apiKey, onChange])

  // When provider changes, pick a default model for that provider
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider)
    const suggestions = config?.suggested_models[newProvider]
    if (suggestions?.length) {
      setModel(suggestions[0])
    }
    setApiKey('')
  }

  if (isLoading) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-3 text-sm text-gray-400">
        Loading LLM config...
      </div>
    )
  }

  const suggestedModels = config?.suggested_models[provider] || []
  const hasEnvKey = provider === 'anthropic'
    ? config?.has_anthropic_key
    : config?.has_openai_key

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-3 space-y-3">
      <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">LLM Configuration</div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Provider */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Provider</label>
          <select
            value={provider}
            onChange={(e) => handleProviderChange(e.target.value)}
            disabled={disabled}
            className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-sm text-gray-200 disabled:opacity-50"
          >
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="openai">OpenAI</option>
          </select>
        </div>

        {/* Model */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Model</label>
          <input
            type="text"
            list="model-suggestions"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={disabled}
            placeholder="Model name"
            className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-sm text-gray-200 disabled:opacity-50 font-mono"
          />
          <datalist id="model-suggestions">
            {suggestedModels.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>

        {/* API Key */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            API Key
            {hasEnvKey && !apiKey && (
              <span className="ml-1 text-green-500">(env var set)</span>
            )}
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={disabled}
            placeholder={hasEnvKey ? 'Using environment key' : 'Enter API key'}
            className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-sm text-gray-200 disabled:opacity-50"
          />
        </div>
      </div>
    </div>
  )
}
