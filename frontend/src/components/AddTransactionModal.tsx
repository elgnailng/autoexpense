import { useState, useEffect } from 'react'
import { useCategories, useCreateTransaction } from '../hooks/useApi'

interface AddTransactionModalProps {
  onClose: () => void
  onCreated?: () => void
}

type EditableStatus = 'full' | 'partial' | 'personal'

const STATUS_OPTIONS: { value: EditableStatus; label: string; color: string; activeBg: string }[] = [
  { value: 'full', label: 'Business', color: 'text-green-400', activeBg: 'bg-green-900/60 border-green-600' },
  { value: 'partial', label: 'Partial', color: 'text-cyan-400', activeBg: 'bg-cyan-900/60 border-cyan-600' },
  { value: 'personal', label: 'Personal', color: 'text-gray-400', activeBg: 'bg-gray-700 border-gray-500' },
]

function formatCurrency(amount: number): string {
  return '$' + Math.abs(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function AddTransactionModal({ onClose, onCreated }: AddTransactionModalProps) {
  const { data: categories } = useCategories()
  const createMutation = useCreateTransaction()

  const [merchantName, setMerchantName] = useState('')
  const [amount, setAmount] = useState('')
  const [txnDate, setTxnDate] = useState(() => new Date().toISOString().split('T')[0])
  const [institution, setInstitution] = useState('Manual')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState<EditableStatus>('full')
  const [deductibleAmount, setDeductibleAmount] = useState('')
  const [isCredit, setIsCredit] = useState(false)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Set default category when categories load
  useEffect(() => {
    if (categories?.length && !category) {
      setCategory(categories[0])
    }
  }, [categories, category])

  // Lock body scroll
  useEffect(() => {
    const original = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = original }
  }, [])

  const parsedAmount = parseFloat(amount) || 0

  const handleSubmit = async () => {
    setError(null)

    if (!merchantName.trim()) {
      setError('Merchant name is required.')
      return
    }
    if (parsedAmount <= 0) {
      setError('Amount must be greater than zero.')
      return
    }
    if (!txnDate) {
      setError('Date is required.')
      return
    }
    if (!category) {
      setError('Category is required.')
      return
    }

    const partialAmt = status === 'partial' ? parseFloat(deductibleAmount) : undefined
    if (status === 'partial') {
      if (partialAmt == null || isNaN(partialAmt) || partialAmt < 0) {
        setError('Deductible amount is required for partial status.')
        return
      }
      if (partialAmt > parsedAmount) {
        setError('Deductible amount cannot exceed the transaction amount.')
        return
      }
    }

    try {
      await createMutation.mutateAsync({
        merchant_name: merchantName.trim(),
        original_amount: parsedAmount,
        transaction_date: txnDate,
        category,
        deductible_status: status,
        deductible_amount: partialAmt,
        institution: institution.trim() || 'Manual',
        notes: notes.trim(),
        is_credit: isCredit,
      })
      onCreated?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create transaction')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

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
          <div className="flex justify-between items-center">
            <h3 className="text-base font-semibold text-gray-100">Add Transaction</h3>
            <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-300">Close</button>
          </div>
        </div>

        {/* Scrollable form */}
        <div
          className="overflow-y-auto overscroll-contain flex-1 min-h-0"
          style={{ WebkitOverflowScrolling: 'touch' }}
        >
          <div className="px-5 pt-4 pb-12 space-y-3">
            {/* Merchant name */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Merchant Name</div>
              <input
                type="text"
                value={merchantName}
                onChange={(e) => setMerchantName(e.target.value)}
                placeholder="e.g. Staples, Home Depot"
                className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2.5 focus:outline-none focus:border-blue-500"
                autoFocus
              />
            </div>

            {/* Amount + Date row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Amount</div>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                    className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 pl-7 pr-3 py-2.5 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Date</div>
                <input
                  type="date"
                  value={txnDate}
                  onChange={(e) => setTxnDate(e.target.value)}
                  className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2.5 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Institution */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Institution</div>
              <input
                type="text"
                value={institution}
                onChange={(e) => setInstitution(e.target.value)}
                placeholder="Manual"
                className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2.5 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Category */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Category</div>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2.5 focus:outline-none focus:border-blue-500"
              >
                {(categories || []).map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            {/* Deductible status */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Deductible Status</div>
              <div className="grid grid-cols-3 gap-2">
                {STATUS_OPTIONS.map(({ value, label, color, activeBg }) => (
                  <button
                    key={value}
                    onClick={() => setStatus(value)}
                    className={`rounded-lg py-2.5 text-sm font-medium border transition-colors ${
                      status === value
                        ? `${activeBg} ${color}`
                        : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Partial amount */}
            {status === 'partial' && (
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Deductible Amount</div>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max={parsedAmount}
                    value={deductibleAmount}
                    onChange={(e) => setDeductibleAmount(e.target.value)}
                    placeholder="0.00"
                    className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 pl-7 pr-3 py-2.5 focus:outline-none focus:border-blue-500"
                  />
                </div>
                {parsedAmount > 0 && (
                  <div className="text-[10px] text-gray-500 mt-1">Max: {formatCurrency(parsedAmount)}</div>
                )}
              </div>
            )}

            {/* Is credit */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isCredit}
                onChange={(e) => setIsCredit(e.target.checked)}
                className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-300">This is a credit/refund</span>
            </label>

            {/* Notes */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Notes</div>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes..."
                rows={2}
                maxLength={1000}
                className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2 focus:outline-none focus:border-blue-500 resize-none"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-lg p-2.5 bg-red-900/30 border border-red-700 text-xs text-red-300">
                {error}
              </div>
            )}

            {/* Submit / Cancel */}
            <div className="flex gap-3 pt-1">
              <button
                onClick={handleSubmit}
                disabled={createMutation.isPending}
                className="flex-1 rounded-lg py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:bg-blue-900 disabled:text-blue-400 transition-colors"
              >
                {createMutation.isPending ? 'Adding...' : 'Add Transaction'}
              </button>
              <button
                onClick={onClose}
                disabled={createMutation.isPending}
                className="flex-1 rounded-lg py-2.5 text-sm font-medium bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
