import { useState } from 'react'
import { useCategories } from '../../hooks/useApi'
import type { DeductionRule } from '../../types'

interface DeductionRuleEditorProps {
  initial?: DeductionRule
  onSave: (rule: Omit<DeductionRule, 'index'>) => void
  onCancel: () => void
  isNew?: boolean
}

export default function DeductionRuleEditor({
  initial,
  onSave,
  onCancel,
  isNew = false,
}: DeductionRuleEditorProps) {
  const { data: categories } = useCategories()
  const [name, setName] = useState(initial?.name ?? '')
  const [merchantPattern, setMerchantPattern] = useState(initial?.merchant_pattern ?? '')
  const [deductibleStatus, setDeductibleStatus] = useState<'full' | 'partial' | 'personal'>(
    initial?.deductible_status ?? 'partial'
  )
  const [method, setMethod] = useState<'full' | 'percentage' | 'fixed_monthly' | 'personal'>(
    initial?.method ?? 'full'
  )
  const [amount, setAmount] = useState(initial?.amount ?? 0)
  const [percentage, setPercentage] = useState(initial?.percentage ?? 50)
  const [category, setCategory] = useState(initial?.category ?? '')
  const [startDate, setStartDate] = useState(initial?.start_date ?? '')
  const [endDate, setEndDate] = useState(initial?.end_date ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')

  const handleSave = () => {
    if (!name.trim() || !merchantPattern.trim()) return

    const rule: Omit<DeductionRule, 'index'> = {
      name: name.trim(),
      merchant_pattern: merchantPattern.trim(),
      deductible_status: deductibleStatus,
      method,
    }

    if (category) rule.category = category
    if (method === 'fixed_monthly') rule.amount = amount
    if (method === 'percentage') rule.percentage = percentage
    if (startDate) rule.start_date = startDate
    if (endDate) rule.end_date = endDate
    if (notes.trim()) rule.notes = notes.trim()

    onSave(rule)

    if (isNew) {
      setName('')
      setMerchantPattern('')
      setDeductibleStatus('partial')
      setMethod('full')
      setAmount(0)
      setPercentage(50)
      setCategory('')
      setStartDate('')
      setEndDate('')
      setNotes('')
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Rule name"
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          value={merchantPattern}
          onChange={(event) => setMerchantPattern(event.target.value)}
          placeholder="Merchant pattern (keyword match)"
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <select
          value={deductibleStatus}
          onChange={(event) => setDeductibleStatus(event.target.value as 'full' | 'partial' | 'personal')}
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="full">Full</option>
          <option value="partial">Partial</option>
          <option value="personal">Personal</option>
        </select>
        <select
          value={method}
          onChange={(event) =>
            setMethod(event.target.value as 'full' | 'percentage' | 'fixed_monthly' | 'personal')
          }
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="full">Full</option>
          <option value="percentage">Percentage</option>
          <option value="fixed_monthly">Fixed Monthly</option>
          <option value="personal">Personal (0%)</option>
        </select>
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Category (optional)</option>
          {categories?.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>

      {method === 'fixed_monthly' && (
        <div>
          <label className="text-xs text-gray-400">Monthly cap ($)</label>
          <input
            type="number"
            min={0}
            step={1}
            value={amount}
            onChange={(event) => setAmount(parseFloat(event.target.value) || 0)}
            className="w-full bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm mt-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}
      {method === 'percentage' && (
        <div>
          <label className="text-xs text-gray-400">Percentage (%)</label>
          <input
            type="number"
            min={0}
            max={100}
            step={5}
            value={percentage}
            onChange={(event) => setPercentage(parseFloat(event.target.value) || 0)}
            className="w-full bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm mt-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <input
          type="date"
          value={startDate}
          onChange={(event) => setStartDate(event.target.value)}
          placeholder="Start date"
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          type="date"
          value={endDate}
          onChange={(event) => setEndDate(event.target.value)}
          placeholder="End date"
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Notes (optional)"
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="flex gap-2 pt-1">
        <button
          onClick={handleSave}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-medium transition-colors"
        >
          {isNew ? 'Add Rule' : 'Save'}
        </button>
        {!isNew && (
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-sm transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}
