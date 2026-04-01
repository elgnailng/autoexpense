import { useStatus, useSummary } from '../hooks/useApi'

function formatCurrency(amount: number | string): string {
  return '$' + Number(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function AccountantOverview() {
  const { data: status, isLoading: statusLoading } = useStatus()
  const { data: summary, isLoading: summaryLoading } = useSummary()

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Expense Overview</h1>

      {statusLoading ? (
        <div className="text-gray-500">Loading...</div>
      ) : status ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Total Transactions</div>
            <div className="text-2xl font-bold text-gray-100">{status.categorized_count}</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Total Spend</div>
            <div className="text-2xl font-bold text-gray-100">{formatCurrency(summary?.totals?.total_spend ?? 0)}</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Total Deductible</div>
            <div className="text-2xl font-bold text-green-400">{formatCurrency(status.total_deductible)}</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Pending Review</div>
            <div className={`text-2xl font-bold ${status.review_count > 0 ? 'text-yellow-400' : 'text-gray-100'}`}>{status.review_count}</div>
          </div>
        </div>
      ) : null}

      <h2 className="text-lg font-semibold mb-3">Category Summary</h2>
      {summaryLoading ? (
        <div className="text-gray-500">Loading summary...</div>
      ) : summary?.by_category && summary.by_category.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-400 uppercase border-b border-gray-700">
              <tr>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3 text-right">Count</th>
                <th className="px-4 py-3 text-right">Total Spent</th>
                <th className="px-4 py-3 text-right">Total Deductible</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {summary.by_category.map((cat) => (
                <tr key={cat.category} className="hover:bg-gray-800/50">
                  <td className="px-4 py-3 text-gray-200">{cat.category}</td>
                  <td className="px-4 py-3 text-right text-gray-300">{cat.transaction_count}</td>
                  <td className="px-4 py-3 text-right font-mono text-gray-300">{formatCurrency(cat.total_original)}</td>
                  <td className="px-4 py-3 text-right font-mono text-green-400">{formatCurrency(cat.total_deductible)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-gray-500">No category data available.</div>
      )}
    </div>
  )
}
