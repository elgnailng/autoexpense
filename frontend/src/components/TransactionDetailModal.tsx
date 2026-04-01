import { useEffect, useState } from 'react'
import type { Transaction, ReviewDecision } from '../types'
import { useSubmitReview, useCategories, useFlagTransaction } from '../hooks/useApi'
import { useAuth } from '../contexts/AuthContext'
import FlagModal from './FlagModal'

interface TransactionDetailModalProps {
  transaction: Transaction
  onClose: () => void
  onUpdated?: () => void
}

function statusColor(status: Transaction['deductible_status']): string {
  switch (status) {
    case 'full': return 'text-green-400'
    case 'partial': return 'text-cyan-400'
    case 'personal': return 'text-gray-400'
    case 'needs_review': return 'text-yellow-400'
    default: return 'text-gray-400'
  }
}

function statusBadgeBg(status: Transaction['deductible_status']): string {
  switch (status) {
    case 'full': return 'bg-green-900/50 border-green-700'
    case 'partial': return 'bg-cyan-900/50 border-cyan-700'
    case 'personal': return 'bg-gray-800 border-gray-600'
    case 'needs_review': return 'bg-yellow-900/50 border-yellow-700'
    default: return 'bg-gray-800 border-gray-600'
  }
}

function formatCurrency(amount: number | string): string {
  return '$' + Math.abs(Number(amount)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function sourceInfo(ruleApplied: string): { label: string; tag: string; color: string; bgColor: string } {
  if (!ruleApplied) return { label: 'No rule', tag: '?', color: 'text-gray-500', bgColor: 'bg-gray-800 border-gray-600' }
  if (ruleApplied.startsWith('llm:')) {
    const model = ruleApplied.slice(4)
    return { label: model, tag: 'LLM', color: 'text-purple-400', bgColor: 'bg-purple-900/40 border-purple-700' }
  }
  if (ruleApplied.startsWith('memory:')) {
    const type = ruleApplied.slice(7)
    return { label: `Merchant memory (${type})`, tag: 'Memory', color: 'text-blue-400', bgColor: 'bg-blue-900/40 border-blue-700' }
  }
  return { label: ruleApplied, tag: 'Rule', color: 'text-amber-400', bgColor: 'bg-amber-900/40 border-amber-700' }
}

type EditableStatus = 'full' | 'partial' | 'personal'

const STATUS_OPTIONS: { value: EditableStatus; label: string; color: string; activeBg: string }[] = [
  { value: 'full', label: 'Business', color: 'text-green-400', activeBg: 'bg-green-900/60 border-green-600' },
  { value: 'partial', label: 'Partial', color: 'text-cyan-400', activeBg: 'bg-cyan-900/60 border-cyan-600' },
  { value: 'personal', label: 'Personal', color: 'text-gray-400', activeBg: 'bg-gray-700 border-gray-500' },
]

export default function TransactionDetailModal({ transaction: t, onClose, onUpdated }: TransactionDetailModalProps) {
  const source = sourceInfo(t.rule_applied)
  const hasNotes = t.notes && t.notes.trim().length > 0
  const isLLM = t.rule_applied?.startsWith('llm:')
  const confidencePct = t.confidence != null ? (t.confidence * 100).toFixed(0) : null

  // Edit mode state
  const [editing, setEditing] = useState(false)
  const [editCategory, setEditCategory] = useState(t.category || 'Other expenses')
  const [editStatus, setEditStatus] = useState<EditableStatus>(
    t.deductible_status === 'needs_review' ? 'personal' : t.deductible_status as EditableStatus
  )
  const [editAmount, setEditAmount] = useState(t.deductible_amount ?? 0)
  const [editNotes, setEditNotes] = useState(t.notes || '')
  const [saveError, setSaveError] = useState<string | null>(null)

  const submitReview = useSubmitReview()
  const { data: categories } = useCategories()
  const { user } = useAuth()
  const flagMutation = useFlagTransaction()
  const [showFlagModal, setShowFlagModal] = useState(false)
  const isOwner = user?.role === 'owner'
  const canFlag = user?.role === 'accountant' || user?.role === 'owner'

  // Compute deductible amount when status changes
  useEffect(() => {
    if (!editing) return
    if (editStatus === 'full') {
      setEditAmount(Math.abs(Number(t.original_amount)))
    } else if (editStatus === 'personal') {
      setEditAmount(0)
    }
    // partial: keep user-entered amount
  }, [editStatus, editing, t.original_amount])

  // Lock body scroll when modal is open
  useEffect(() => {
    const original = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = original }
  }, [])

  const handleSave = async () => {
    setSaveError(null)
    const decision: ReviewDecision = {
      category: editCategory,
      deductible_status: editStatus,
      deductible_amount: editAmount,
      notes: editNotes,
    }
    try {
      await submitReview.mutateAsync({ id: t.transaction_id, decision })
      setEditing(false)
      onUpdated?.()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save')
    }
  }

  const handleStartEdit = () => {
    setEditCategory(t.category || 'Other expenses')
    setEditStatus(t.deductible_status === 'needs_review' ? 'personal' : t.deductible_status as EditableStatus)
    setEditAmount(t.deductible_amount ?? 0)
    setEditNotes(t.notes || '')
    setSaveError(null)
    setEditing(true)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div
        className="relative w-full md:max-w-lg md:mx-4 bg-gray-900 border border-gray-700 rounded-t-2xl md:rounded-2xl flex flex-col max-h-[85dvh] animate-slide-up"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag handle (mobile) */}
        <div className="md:hidden flex justify-center pt-3 pb-1 shrink-0">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        {/* Header */}
        <div className="px-5 pt-3 pb-3 border-b border-gray-800 shrink-0">
          <div className="flex justify-between items-start">
            <div className="flex-1 min-w-0 mr-3">
              <h3 className="text-base font-semibold text-gray-100 break-words">
                {t.merchant_normalized || t.merchant_raw || 'Unknown'}
              </h3>
              <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                <span>{t.transaction_date}</span>
                <span className="text-gray-600">|</span>
                <span>{t.institution}</span>
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-lg font-mono font-semibold text-gray-100">
                {t.is_credit ? '-' : ''}{formatCurrency(t.original_amount)}
              </div>
              <div className="flex items-center gap-3 mt-1 justify-end">
                {!editing && isOwner && (
                  <button
                    onClick={handleStartEdit}
                    className="text-xs text-blue-400 hover:text-blue-300"
                  >
                    Edit
                  </button>
                )}
                {!editing && canFlag && (
                  <button
                    onClick={() => setShowFlagModal(true)}
                    className="bg-amber-600/20 border border-amber-600 text-amber-400 hover:bg-amber-600/30 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                  >
                    Flag for Review
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="text-xs text-gray-500 hover:text-gray-300"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Scrollable content */}
        <div
          className="overflow-y-auto overscroll-contain flex-1 min-h-0"
          style={{ WebkitOverflowScrolling: 'touch' }}
        >
          <div className="px-5 pt-4 pb-12 space-y-3">
            {editing ? (
              /* ── Edit Mode ── */
              <>
                {/* Category select */}
                <div>
                  <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Category</div>
                  <select
                    value={editCategory}
                    onChange={(e) => setEditCategory(e.target.value)}
                    className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2.5 focus:outline-none focus:border-blue-500"
                  >
                    {(categories || []).map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>

                {/* Status buttons */}
                <div>
                  <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Deductible Status</div>
                  <div className="grid grid-cols-3 gap-2">
                    {STATUS_OPTIONS.map(({ value, label, color, activeBg }) => (
                      <button
                        key={value}
                        onClick={() => setEditStatus(value)}
                        className={`rounded-lg py-2.5 text-sm font-medium border transition-colors ${
                          editStatus === value
                            ? `${activeBg} ${color}`
                            : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Deductible amount (for partial) */}
                {editStatus === 'partial' && (
                  <div>
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Deductible Amount</div>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max={Math.abs(Number(t.original_amount))}
                        value={editAmount}
                        onChange={(e) => setEditAmount(Number(e.target.value))}
                        className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 pl-7 pr-3 py-2.5 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="text-[10px] text-gray-500 mt-1">
                      Max: {formatCurrency(t.original_amount)}
                    </div>
                  </div>
                )}

                {/* Notes */}
                <div>
                  <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Notes</div>
                  <textarea
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    placeholder="Optional notes about this decision..."
                    rows={2}
                    className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2 focus:outline-none focus:border-blue-500 resize-none"
                  />
                </div>

                {/* Error */}
                {saveError && (
                  <div className="rounded-lg p-2.5 bg-red-900/30 border border-red-700 text-xs text-red-300">
                    {saveError}
                  </div>
                )}

                {/* Save / Cancel */}
                <div className="flex gap-3 pt-1">
                  <button
                    onClick={handleSave}
                    disabled={submitReview.isPending}
                    className="flex-1 rounded-lg py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:bg-blue-900 disabled:text-blue-400 transition-colors"
                  >
                    {submitReview.isPending ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    onClick={() => setEditing(false)}
                    disabled={submitReview.isPending}
                    className="flex-1 rounded-lg py-2.5 text-sm font-medium bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              /* ── View Mode ── */
              <>
                <div className="grid grid-cols-2 gap-3">
                  {/* Category */}
                  <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Category</div>
                    <div className="text-sm text-gray-200 font-medium">{t.category || 'Uncategorized'}</div>
                  </div>

                  {/* Status */}
                  <div className={`rounded-lg p-3 border ${statusBadgeBg(t.deductible_status)}`}>
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Status</div>
                    <div className={`text-sm font-medium ${statusColor(t.deductible_status)}`}>
                      {t.deductible_status}
                    </div>
                  </div>

                  {/* Confidence */}
                  {confidencePct && (
                    <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
                      <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Confidence</div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-700 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${
                              Number(confidencePct) >= 70 ? 'bg-green-500' : Number(confidencePct) >= 50 ? 'bg-yellow-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${confidencePct}%` }}
                          />
                        </div>
                        <span className="text-sm text-gray-200 font-medium">{confidencePct}%</span>
                      </div>
                    </div>
                  )}

                  {/* Deductible */}
                  <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Deductible</div>
                    <div className="text-sm text-gray-200 font-medium">{formatCurrency(t.deductible_amount)}</div>
                  </div>
                </div>

                {/* Source */}
                <div className={`rounded-lg p-3 border ${source.bgColor}`}>
                  <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Categorized By</div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${source.bgColor} ${source.color}`}>
                      {source.tag}
                    </span>
                    <span className={`text-sm font-mono ${source.color}`}>{source.label}</span>
                  </div>
                </div>

                {/* LLM Reasoning */}
                {hasNotes ? (
                  <div className="rounded-lg p-4 bg-gray-800 border border-gray-700">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">LLM Reasoning</div>
                    <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                      {t.notes}
                    </div>
                  </div>
                ) : isLLM ? (
                  <div className="rounded-lg p-3 bg-gray-800/50 border border-gray-700/50">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">LLM Reasoning</div>
                    <div className="text-xs text-gray-500 italic">
                      No reasoning provided by the model for this transaction.
                    </div>
                  </div>
                ) : null}

                {/* Extra details */}
                {(t.source_file || t.description_raw) && (
                  <div className="rounded-lg p-3 bg-gray-800/50 border border-gray-700/50 space-y-1">
                    {t.source_file && (
                      <div className="text-xs break-all">
                        <span className="text-gray-500">Source: </span>
                        <span className="text-gray-400 font-mono">{t.source_file}</span>
                      </div>
                    )}
                    {t.description_raw && (
                      <div className="text-xs break-all">
                        <span className="text-gray-500">Raw: </span>
                        <span className="text-gray-400">{t.description_raw}</span>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {showFlagModal && (
        <FlagModal
          merchantName={t.merchant_normalized || t.merchant_raw || 'Unknown'}
          isPending={flagMutation.isPending}
          onSubmit={async (reason) => {
            await flagMutation.mutateAsync({ id: t.transaction_id, reason })
            setShowFlagModal(false)
            onUpdated?.()
            onClose()
          }}
          onClose={() => setShowFlagModal(false)}
        />
      )}
    </div>
  )
}
