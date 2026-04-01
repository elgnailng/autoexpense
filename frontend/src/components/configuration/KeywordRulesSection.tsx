import { useState } from 'react'
import {
  useAddKeywordRule,
  useDeleteKeywordRule,
  useKeywordRules,
  useUpdateKeywordRule,
} from '../../hooks/useApi'
import KeywordRuleEditor from './KeywordRuleEditor'
import { formatKeywordConfidence } from './utils'

interface KeywordRulesSectionProps {
  locked: boolean
}

export default function KeywordRulesSection({ locked }: KeywordRulesSectionProps) {
  const { data: rules, isLoading } = useKeywordRules()
  const addRule = useAddKeywordRule()
  const updateRule = useUpdateKeywordRule()
  const deleteRule = useDeleteKeywordRule()
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  if (isLoading) return <div className="text-gray-500">Loading rules...</div>

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        {rules?.map((rule) => (
          <div key={rule.index}>
            {editingIndex === rule.index ? (
              <KeywordRuleEditor
                initial={rule}
                onSave={(updatedRule) => {
                  updateRule.mutate({ index: rule.index, rule: updatedRule })
                  setEditingIndex(null)
                }}
                onCancel={() => setEditingIndex(null)}
              />
            ) : (
              <div className="bg-gray-800 rounded-lg p-3 border border-gray-700 flex items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap gap-1.5 mb-1">
                    {rule.keywords.map((keyword) => (
                      <span
                        key={keyword}
                        className="bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded text-xs font-mono"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                  <div className="text-sm text-gray-400">
                    {rule.category} &middot; {formatKeywordConfidence(rule)}
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => setEditingIndex(rule.index)}
                    disabled={locked}
                    className="text-xs px-2.5 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => {
                      if (confirm('Delete this rule?')) deleteRule.mutate(rule.index)
                    }}
                    disabled={locked}
                    className="text-xs px-2.5 py-1.5 bg-red-900/50 hover:bg-red-800/50 text-red-400 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Delete
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {!locked && (
        <div className="border-t border-gray-700 pt-4">
          <h3 className="text-sm font-semibold text-gray-300 mb-2">Add New Rule</h3>
          <KeywordRuleEditor onSave={(rule) => addRule.mutate(rule)} onCancel={() => {}} isNew />
        </div>
      )}
    </div>
  )
}
