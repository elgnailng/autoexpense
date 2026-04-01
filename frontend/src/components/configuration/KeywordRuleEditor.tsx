import { useState } from 'react'
import { useCategories } from '../../hooks/useApi'
import type { KeywordRule } from '../../types'

interface KeywordRuleEditorProps {
  initial?: KeywordRule
  onSave: (rule: Omit<KeywordRule, 'index'>) => void
  onCancel: () => void
  isNew?: boolean
}

export default function KeywordRuleEditor({
  initial,
  onSave,
  onCancel,
  isNew = false,
}: KeywordRuleEditorProps) {
  const { data: categories } = useCategories()
  const [keywords, setKeywords] = useState(initial?.keywords.join(', ') ?? '')
  const [category, setCategory] = useState(initial?.category ?? '')
  const [confidence, setConfidence] = useState(initial?.confidence ?? 0.9)

  const handleSave = () => {
    const keywordList = keywords
      .split(',')
      .map((keyword) => keyword.trim())
      .filter(Boolean)

    if (keywordList.length === 0 || !category) return

    onSave({ keywords: keywordList, category, confidence })

    if (isNew) {
      setKeywords('')
      setCategory('')
      setConfidence(0.9)
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-3 border border-gray-600 space-y-2">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <input
          value={keywords}
          onChange={(event) => setKeywords(event.target.value)}
          placeholder="Keywords (comma-separated)"
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select category...</option>
          {categories?.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <div className="flex gap-2">
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={confidence}
            onChange={(event) => setConfidence(parseFloat(event.target.value) || 0)}
            className="bg-gray-900 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm w-20 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSave}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-medium transition-colors"
          >
            {isNew ? 'Add' : 'Save'}
          </button>
          {!isNew && (
            <button
              onClick={onCancel}
              className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-sm transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
