import { useState } from 'react'
import {
  useAddDeductionRule,
  useDeductionRules,
  useDeleteDeductionRule,
  useUpdateDeductionRule,
} from '../../hooks/useApi'
import DeductionRuleEditor from './DeductionRuleEditor'
import { formatMethod, statusColor } from './utils'

interface DeductionRulesSectionProps {
  locked: boolean
}

export default function DeductionRulesSection({ locked }: DeductionRulesSectionProps) {
  const { data: rules, isLoading } = useDeductionRules()
  const addRule = useAddDeductionRule()
  const updateRule = useUpdateDeductionRule()
  const deleteRule = useDeleteDeductionRule()
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  if (isLoading) return <div className="text-gray-500">Loading deduction rules...</div>

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        {rules?.map((rule) => (
          <div key={rule.index}>
            {editingIndex === rule.index ? (
              <DeductionRuleEditor
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
                  <div className="font-medium text-gray-200 text-sm">{rule.name}</div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    <span className="font-mono">{rule.merchant_pattern}</span>
                    {' '}&middot;{' '}
                    <span className={statusColor(rule.deductible_status)}>{rule.deductible_status}</span>
                    {' '}&middot;{' '}
                    {formatMethod(rule)}
                    {rule.start_date && <span> &middot; from {rule.start_date}</span>}
                    {rule.end_date && <span> &middot; until {rule.end_date}</span>}
                  </div>
                  {rule.notes && <div className="text-xs text-gray-500 mt-0.5">{rule.notes}</div>}
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
                      if (confirm('Delete this deduction rule?')) deleteRule.mutate(rule.index)
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
          <h3 className="text-sm font-semibold text-gray-300 mb-2">Add New Deduction Rule</h3>
          <DeductionRuleEditor onSave={(rule) => addRule.mutate(rule)} onCancel={() => {}} isNew />
        </div>
      )}
    </div>
  )
}
