import { useEffect, useState } from 'react'
import type { ReviewTransaction } from '../types'

interface PartialAmountModalProps {
  isOpen: boolean
  transaction: ReviewTransaction
  category: string
  onConfirm: (amount: number, notes: string) => void
  onCancel: () => void
  isSubmitting?: boolean
}

export default function PartialAmountModal({
  isOpen,
  transaction,
  category,
  onConfirm,
  onCancel,
  isSubmitting = false,
}: PartialAmountModalProps) {
  const originalAmount = Number(transaction.original_amount) || 0
  const deductibleAmt = Number(transaction.deductible_amount) || 0
  const defaultAmount = deductibleAmt > 0 && deductibleAmt < originalAmount ? deductibleAmt : originalAmount
  const [amount, setAmount] = useState(defaultAmount)
  const [notes, setNotes] = useState('')

  useEffect(() => {
    if (!isOpen) return
    setAmount(defaultAmount)
    setNotes('')
  }, [defaultAmount, isOpen, transaction.transaction_id])

  if (!isOpen) return null

  const handleConfirm = () => {
    if (isSubmitting) return
    const clampedAmount = Math.max(0, Math.min(amount, originalAmount))
    onConfirm(clampedAmount, notes)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={isSubmitting ? undefined : onCancel}
      />

      <div className="relative w-full max-w-sm mx-4 mb-4 sm:mb-0 bg-gray-800 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden">
        <div className="p-5 space-y-4">
          <div>
            <h3 className="text-lg font-bold text-gray-100">Partial Deduction</h3>
            <p className="text-sm text-gray-400 mt-1">{transaction.merchant_normalized}</p>
          </div>

          <div className="bg-gray-900/50 rounded-lg p-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Original amount</span>
              <span className="text-lg font-bold text-white">
                ${originalAmount.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between items-center mt-1">
              <span className="text-sm text-gray-400">Category</span>
              <span className="text-sm text-gray-300">{category}</span>
            </div>
          </div>

          <div>
            <label htmlFor="partial-amount" className="block text-sm font-medium text-gray-300 mb-1">
              Deductible amount
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-lg">$</span>
              <input
                id="partial-amount"
                type="number"
                min={0}
                max={originalAmount}
                step={0.01}
                value={amount}
                onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
                disabled={isSubmitting}
                className="w-full pl-8 pr-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white text-lg font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:cursor-not-allowed disabled:opacity-60"
                autoFocus
              />
            </div>
            {amount > originalAmount && (
              <p className="text-xs text-red-400 mt-1">
                Cannot exceed original amount (${originalAmount.toFixed(2)})
              </p>
            )}
          </div>

          <div>
            <label htmlFor="partial-notes" className="block text-sm font-medium text-gray-300 mb-1">
              Notes (optional)
            </label>
            <input
              id="partial-notes"
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. 50% business use"
              disabled={isSubmitting}
              className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:cursor-not-allowed disabled:opacity-60"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              onClick={onCancel}
              disabled={isSubmitting}
              className="flex-1 py-3 px-4 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={isSubmitting}
              className="flex-1 py-3 px-4 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? 'Saving...' : 'Confirm'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
