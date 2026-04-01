import { useState, useMemo, useEffect } from 'react'
import { useTransactions, useCategories, useBatchUpdate, useBatchFlag, useFlagTransaction } from '../hooks/useApi'
import { useAuth } from '../contexts/AuthContext'
import type { Transaction } from '../types'
import TransactionTable from '../components/TransactionTable'
import BatchActionBar from '../components/BatchActionBar'
import FlagModal from '../components/FlagModal'
import AddTransactionModal from '../components/AddTransactionModal'

type StatusFilter = 'all' | 'review' | 'business' | 'personal'
type SortField = 'date' | 'amount' | 'merchant' | 'category' | 'status'
type SortDir = 'asc' | 'desc'

export default function Transactions() {
  const { user } = useAuth()
  const [institution, setInstitution] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [ruleSourceFilter, setRuleSourceFilter] = useState<string>('')
  const [sortField, setSortField] = useState<SortField>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [offset, setOffset] = useState(0)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const limit = 50

  const { data: categories } = useCategories()
  const batchUpdate = useBatchUpdate()
  const batchFlag = useBatchFlag()
  const flagMutation = useFlagTransaction()
  const [flagTarget, setFlagTarget] = useState<Transaction | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)

  const isAccountant = user?.role === 'accountant'
  const canSelect = !!user
  const canFlag = user?.role === 'accountant' || user?.role === 'owner'

  // Clear selections on filter/pagination change
  useEffect(() => {
    setSelectedIds(new Set())
  }, [institution, statusFilter, categoryFilter, ruleSourceFilter, sortField, sortDir, offset])

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir(field === 'merchant' ? 'asc' : 'desc')
    }
    setOffset(0)
  }

  const params = useMemo(() => {
    const p = new URLSearchParams()
    if (institution) p.set('institution', institution)
    if (statusFilter !== 'all') p.set('status', statusFilter)
    if (categoryFilter) p.set('category', categoryFilter)
    if (ruleSourceFilter) p.set('rule_source', ruleSourceFilter)
    p.set('sort', sortField)
    p.set('sort_dir', sortDir)
    p.set('limit', limit.toString())
    p.set('offset', offset.toString())
    return p
  }, [institution, statusFilter, categoryFilter, ruleSourceFilter, sortField, sortDir, offset])

  const { data, isLoading, refetch } = useTransactions(params)

  const handlePrev = () => setOffset((o) => Math.max(0, o - limit))
  const handleNext = () => {
    if (data && offset + limit < data.total) {
      setOffset((o) => o + limit)
    }
  }

  const formatCurrency = (amount: number) =>
    `$${Math.abs(amount).toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  const handleBatchUpdate = (category: string, deductibleStatus: string, notes: string) => {
    batchUpdate.mutate(
      { transaction_ids: Array.from(selectedIds), category, deductible_status: deductibleStatus, notes },
      { onSuccess: () => { setSelectedIds(new Set()); refetch() } },
    )
  }

  const handleBatchFlag = (reason: string) => {
    batchFlag.mutate(
      { transaction_ids: Array.from(selectedIds), reason },
      { onSuccess: () => { setSelectedIds(new Set()); refetch() } },
    )
  }

  return (
    <div className={`p-4 max-w-5xl mx-auto ${selectedIds.size > 0 ? 'pb-24' : ''}`}>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Transactions</h1>
        <button
          onClick={() => setShowAddModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          + Add Transaction
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={institution}
          onChange={(e) => { setInstitution(e.target.value); setOffset(0) }}
          className="bg-gray-800 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Institutions</option>
          <option value="RBC Visa">RBC Visa</option>
          <option value="BMO Mastercard">BMO Mastercard</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value as StatusFilter); setOffset(0) }}
          className="bg-gray-800 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Statuses</option>
          <option value="review">Pending Review</option>
          <option value="business">Business</option>
          {!isAccountant && <option value="personal">Personal</option>}
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => { setCategoryFilter(e.target.value); setOffset(0) }}
          className="bg-gray-800 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Categories</option>
          {categories?.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>

        <select
          value={ruleSourceFilter}
          onChange={(e) => { setRuleSourceFilter(e.target.value); setOffset(0) }}
          className="bg-gray-800 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Sources</option>
          <option value="llm">LLM</option>
          <option value="keyword">Keyword Rules</option>
          <option value="memory">Merchant Memory</option>
        </select>

        {/* Sort dropdown (visible on all sizes, compact) */}
        <select
          value={`${sortField}-${sortDir}`}
          onChange={(e) => {
            const [f, d] = e.target.value.split('-') as [SortField, SortDir]
            setSortField(f)
            setSortDir(d)
            setOffset(0)
          }}
          className="bg-gray-800 border border-gray-600 text-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="date-desc">Date (Newest)</option>
          <option value="date-asc">Date (Oldest)</option>
          <option value="amount-desc">Amount (High-Low)</option>
          <option value="amount-asc">Amount (Low-High)</option>
          <option value="merchant-asc">Merchant (A-Z)</option>
          <option value="merchant-desc">Merchant (Z-A)</option>
          <option value="category-asc">Category (A-Z)</option>
          <option value="status-asc">Status (A-Z)</option>
        </select>
      </div>

      {/* Transaction list */}
      {isLoading ? (
        <div className="text-gray-500 py-8 text-center">Loading transactions...</div>
      ) : data ? (
        <>
          <div className="flex flex-wrap justify-between items-center text-sm text-gray-400 mb-3">
            <span>
              Showing {offset + 1}--{Math.min(offset + limit, data.total)} of {data.total}
            </span>
            <span className="font-medium text-gray-200">
              Total: {formatCurrency(data.total_amount)}
            </span>
          </div>
          <TransactionTable
            transactions={data.transactions}
            onTransactionUpdated={() => refetch()}
            sortField={sortField}
            sortDir={sortDir}
            onSort={toggleSort}
            selectable={canSelect}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
            canFlag={canFlag}
            onFlagTransaction={(t) => setFlagTarget(t)}
          />

          {/* Pagination */}
          <div className="flex justify-between items-center mt-4">
            <button
              onClick={handlePrev}
              disabled={offset === 0}
              className="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 text-gray-200 rounded px-4 py-2 text-sm"
            >
              Previous
            </button>
            <button
              onClick={handleNext}
              disabled={!data || offset + limit >= data.total}
              className="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 text-gray-200 rounded px-4 py-2 text-sm"
            >
              Next
            </button>
          </div>
        </>
      ) : (
        <div className="text-gray-500 py-8 text-center">
          No transactions found. Run the pipeline to import data.
        </div>
      )}

      {/* Batch action bar */}
      {canSelect && (
        <BatchActionBar
          selectedCount={selectedIds.size}
          role={user?.role ?? 'owner'}
          categories={categories}
          onBatchUpdate={handleBatchUpdate}
          onBatchFlag={canFlag ? handleBatchFlag : undefined}
          onClear={() => setSelectedIds(new Set())}
          isPending={batchUpdate.isPending || batchFlag.isPending}
        />
      )}

      {/* Flag modal */}
      {flagTarget && (
        <FlagModal
          merchantName={flagTarget.merchant_normalized || flagTarget.merchant_raw || 'Unknown'}
          isPending={flagMutation.isPending}
          onSubmit={async (reason) => {
            await flagMutation.mutateAsync({ id: flagTarget.transaction_id, reason })
            setFlagTarget(null)
            refetch()
          }}
          onClose={() => setFlagTarget(null)}
        />
      )}

      {/* Add transaction modal */}
      {showAddModal && (
        <AddTransactionModal
          onClose={() => setShowAddModal(false)}
          onCreated={() => {
            setShowAddModal(false)
            refetch()
          }}
        />
      )}
    </div>
  )
}
