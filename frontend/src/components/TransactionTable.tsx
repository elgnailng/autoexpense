import { useState } from 'react'
import type { Transaction } from '../types'
import TransactionDetailModal from './TransactionDetailModal'

type SortField = 'date' | 'amount' | 'merchant' | 'category' | 'status'
type SortDir = 'asc' | 'desc'

interface TransactionTableProps {
  transactions: Transaction[]
  onTransactionUpdated?: () => void
  sortField?: SortField
  sortDir?: SortDir
  onSort?: (field: SortField) => void
  selectable?: boolean
  selectedIds?: Set<string>
  onSelectionChange?: (ids: Set<string>) => void
  canFlag?: boolean
  onFlagTransaction?: (transaction: Transaction) => void
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

function statusBg(status: Transaction['deductible_status']): string {
  switch (status) {
    case 'full': return 'bg-green-900/30 border-green-700'
    case 'partial': return 'bg-cyan-900/30 border-cyan-700'
    case 'personal': return 'bg-gray-800/50 border-gray-700'
    case 'needs_review': return 'bg-yellow-900/30 border-yellow-700'
    default: return 'bg-gray-800/50 border-gray-700'
  }
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })
}

function formatCurrency(amount: number | string): string {
  return '$' + Math.abs(Number(amount)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function sourceTag(ruleApplied: string): { tag: string; color: string } | null {
  if (!ruleApplied) return null
  if (ruleApplied.startsWith('llm:')) return { tag: 'LLM', color: 'bg-purple-900/50 text-purple-400 border-purple-700' }
  if (ruleApplied.startsWith('memory:')) return { tag: 'MEM', color: 'bg-blue-900/50 text-blue-400 border-blue-700' }
  return { tag: 'RULE', color: 'bg-amber-900/50 text-amber-400 border-amber-700' }
}

function SortIcon({ field, sortField, sortDir }: { field: SortField; sortField?: SortField; sortDir?: SortDir }) {
  if (field !== sortField) return <span className="text-gray-600 ml-1">&#x2195;</span>
  return <span className="text-blue-400 ml-1">{sortDir === 'asc' ? '\u2191' : '\u2193'}</span>
}

export default function TransactionTable({ transactions, onTransactionUpdated, sortField, sortDir, onSort, selectable, selectedIds, onSelectionChange, canFlag, onFlagTransaction }: TransactionTableProps) {
  const [selectedTxn, setSelectedTxn] = useState<Transaction | null>(null)

  const allSelected = selectable && transactions.length > 0 && transactions.every(t => selectedIds?.has(t.transaction_id))

  const toggleOne = (id: string) => {
    if (!onSelectionChange || !selectedIds) return
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelectionChange(next)
  }

  const toggleAll = () => {
    if (!onSelectionChange || !selectedIds) return
    if (allSelected) {
      const next = new Set(selectedIds)
      transactions.forEach(t => next.delete(t.transaction_id))
      onSelectionChange(next)
    } else {
      const next = new Set(selectedIds)
      transactions.forEach(t => next.add(t.transaction_id))
      onSelectionChange(next)
    }
  }

  if (transactions.length === 0) {
    return (
      <div className="text-gray-500 text-center py-8">No transactions found.</div>
    )
  }

  return (
    <>
      {/* Mobile: card layout */}
      <div className="md:hidden space-y-3">
        {transactions.map((t) => {
          const source = sourceTag(t.rule_applied)
          return (
            <div
              key={t.transaction_id}
              onClick={() => setSelectedTxn(t)}
              className={`rounded-lg border p-3 cursor-pointer active:scale-[0.98] transition-transform ${statusBg(t.deductible_status)}`}
            >
              <div className="flex justify-between items-start mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  {selectable && (
                    <input
                      type="checkbox"
                      checked={selectedIds?.has(t.transaction_id) ?? false}
                      onChange={() => toggleOne(t.transaction_id)}
                      onClick={(e) => e.stopPropagation()}
                      className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 flex-shrink-0"
                    />
                  )}
                  <span className="font-medium text-gray-200 text-sm truncate">
                    {t.merchant_normalized || t.merchant_raw}
                  </span>
                </div>
                <span className="text-sm font-mono whitespace-nowrap">
                  {t.is_credit ? '-' : ''}{formatCurrency(t.original_amount)}
                </span>
              </div>
              <div className="flex justify-between items-center text-xs text-gray-400">
                <span>{formatDate(t.transaction_date)}</span>
                <span>{t.institution}</span>
              </div>
              <div className="flex justify-between items-center mt-2 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="bg-gray-700 rounded px-2 py-0.5 text-gray-300">
                    {t.category || 'Uncategorized'}
                  </span>
                  {source && (
                    <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${source.color}`}>
                      {source.tag}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${statusColor(t.deductible_status)}`}>
                    {t.deductible_status}
                  </span>
                  {canFlag && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onFlagTransaction?.(t) }}
                      className="text-amber-500 hover:text-amber-400 p-0.5"
                      title="Flag for review"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                        <path d="M3.5 2.75a.75.75 0 00-1.5 0v14.5a.75.75 0 001.5 0v-4.392l1.657-.348a6.449 6.449 0 014.271.572 7.948 7.948 0 005.965.524l2.078-.64A.75.75 0 0018 12.25v-8.5a.75.75 0 00-.904-.734l-2.38.501a7.25 7.25 0 01-4.186-.363l-.502-.2a8.75 8.75 0 00-5.053-.439l-1.475.31V2.75z" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Desktop: table layout */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-gray-400 uppercase border-b border-gray-700">
            <tr>
              {selectable && (
                <th className="px-2 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                  />
                </th>
              )}
              <th className="px-4 py-3 cursor-pointer select-none hover:text-gray-200" onClick={() => onSort?.('date')}>
                Date<SortIcon field="date" sortField={sortField} sortDir={sortDir} />
              </th>
              <th className="px-4 py-3 cursor-pointer select-none hover:text-gray-200" onClick={() => onSort?.('merchant')}>
                Merchant<SortIcon field="merchant" sortField={sortField} sortDir={sortDir} />
              </th>
              <th className="px-4 py-3 text-right cursor-pointer select-none hover:text-gray-200" onClick={() => onSort?.('amount')}>
                Amount<SortIcon field="amount" sortField={sortField} sortDir={sortDir} />
              </th>
              <th className="px-4 py-3 cursor-pointer select-none hover:text-gray-200" onClick={() => onSort?.('category')}>
                Category<SortIcon field="category" sortField={sortField} sortDir={sortDir} />
              </th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3 cursor-pointer select-none hover:text-gray-200" onClick={() => onSort?.('status')}>
                Status<SortIcon field="status" sortField={sortField} sortDir={sortDir} />
              </th>
              {canFlag && <th className="px-2 py-3 w-10"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {transactions.map((t) => {
              const source = sourceTag(t.rule_applied)
              return (
                <tr
                  key={t.transaction_id}
                  onClick={() => setSelectedTxn(t)}
                  className={`hover:bg-gray-800/50 cursor-pointer ${selectedIds?.has(t.transaction_id) ? 'bg-blue-900/20' : ''}`}
                >
                  {selectable && (
                    <td className="px-2 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds?.has(t.transaction_id) ?? false}
                        onChange={() => toggleOne(t.transaction_id)}
                        onClick={(e) => e.stopPropagation()}
                        className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                      />
                    </td>
                  )}
                  <td className="px-4 py-3 whitespace-nowrap text-gray-300">
                    {formatDate(t.transaction_date)}
                  </td>
                  <td className="px-4 py-3 text-gray-200">
                    {t.merchant_normalized || t.merchant_raw}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-gray-200">
                    {t.is_credit ? '-' : ''}{formatCurrency(t.original_amount)}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {t.category || 'Uncategorized'}
                  </td>
                  <td className="px-4 py-3">
                    {source ? (
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${source.color}`}>
                        {source.tag}
                      </span>
                    ) : (
                      <span className="text-gray-600">--</span>
                    )}
                  </td>
                  <td className={`px-4 py-3 font-medium ${statusColor(t.deductible_status)}`}>
                    {t.deductible_status}
                  </td>
                  {canFlag && (
                    <td className="px-2 py-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); onFlagTransaction?.(t) }}
                        className="text-amber-500 hover:text-amber-400 p-1 rounded hover:bg-amber-900/20 transition-colors"
                        title="Flag for review"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                          <path d="M3.5 2.75a.75.75 0 00-1.5 0v14.5a.75.75 0 001.5 0v-4.392l1.657-.348a6.449 6.449 0 014.271.572 7.948 7.948 0 005.965.524l2.078-.64A.75.75 0 0018 12.25v-8.5a.75.75 0 00-.904-.734l-2.38.501a7.25 7.25 0 01-4.186-.363l-.502-.2a8.75 8.75 0 00-5.053-.439l-1.475.31V2.75z" />
                        </svg>
                      </button>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Detail modal */}
      {selectedTxn && (
        <TransactionDetailModal
          transaction={selectedTxn}
          onClose={() => setSelectedTxn(null)}
          onUpdated={() => {
            setSelectedTxn(null)
            onTransactionUpdated?.()
          }}
        />
      )}
    </>
  )
}
