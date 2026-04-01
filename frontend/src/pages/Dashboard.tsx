import { useStatus, useSummary } from '../hooks/useApi'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import AccountantOverview from './AccountantOverview'

function formatCurrency(amount: number | string): string {
  return '$' + Number(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function Dashboard() {
  const { user } = useAuth()
  if (user?.role === 'accountant') return <AccountantOverview />
  return <OwnerHome />
}

// --- Next-action logic ---------------------------------------------------

interface NextAction {
  title: string
  subtitle?: string
  route?: string
  buttonLabel?: string
  buttonClass: string
  bgColor: string
  borderColor: string
}

function getNextAction(state: {
  pipelineRunning: boolean
  hasRaw: boolean
  hasNormalized: boolean
  hasCategorized: boolean
  reviewCount: number
  allReviewed: boolean
}): NextAction {
  if (state.pipelineRunning) {
    return {
      title: 'Pipeline is running',
      subtitle: 'Wait for the current step to complete before taking action.',
      buttonClass: '',
      bgColor: 'bg-yellow-500/5',
      borderColor: 'border-yellow-500/20',
    }
  }
  if (!state.hasRaw) {
    return {
      title: 'Load your bank statements',
      subtitle: 'Extract transactions from your PDF statements to get started.',
      route: '/pipeline',
      buttonLabel: 'Go to Pipeline',
      buttonClass: 'bg-blue-600 hover:bg-blue-500 text-white',
      bgColor: 'bg-blue-500/5',
      borderColor: 'border-blue-500/20',
    }
  }
  if (!state.hasNormalized) {
    return {
      title: 'Transform your transactions',
      subtitle: 'Normalize and deduplicate extracted transactions.',
      route: '/pipeline',
      buttonLabel: 'Go to Pipeline',
      buttonClass: 'bg-blue-600 hover:bg-blue-500 text-white',
      bgColor: 'bg-blue-500/5',
      borderColor: 'border-blue-500/20',
    }
  }
  if (!state.hasCategorized) {
    return {
      title: 'Categorize your transactions',
      subtitle: 'Apply rules and merchant memory to classify expenses.',
      route: '/pipeline',
      buttonLabel: 'Go to Pipeline',
      buttonClass: 'bg-blue-600 hover:bg-blue-500 text-white',
      bgColor: 'bg-blue-500/5',
      borderColor: 'border-blue-500/20',
    }
  }
  if (state.reviewCount > 0) {
    return {
      title: `Review ${state.reviewCount} transaction${state.reviewCount === 1 ? '' : 's'}`,
      subtitle: 'Confirm or correct categories before exporting.',
      route: '/review',
      buttonLabel: 'Start Reviewing',
      buttonClass: 'bg-yellow-600 hover:bg-yellow-500 text-white',
      bgColor: 'bg-yellow-500/5',
      borderColor: 'border-yellow-500/20',
    }
  }
  return {
    title: 'Ready to export',
    subtitle: 'All transactions reviewed. Export your results for tax filing.',
    route: '/export',
    buttonLabel: 'Export Results',
    buttonClass: 'bg-green-600 hover:bg-green-500 text-white',
    bgColor: 'bg-green-500/5',
    borderColor: 'border-green-500/20',
  }
}

// --- Owner home page -----------------------------------------------------

function OwnerHome() {
  const { data: status, isLoading: statusLoading } = useStatus()
  const { data: summary } = useSummary()
  const navigate = useNavigate()

  if (statusLoading) {
    return (
      <div className="p-4 max-w-3xl mx-auto">
        <div className="text-gray-500 mt-8 text-center">Loading...</div>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="p-4 max-w-3xl mx-auto">
        <div className="text-gray-500 mt-8 text-center">Unable to load status.</div>
      </div>
    )
  }

  const raw = status.raw_count
  const normalized = status.normalized_count
  const categorized = status.categorized_count
  const reviewCount = status.review_count
  const totalDeductible = status.total_deductible
  const pipelineRunning = status.pipeline_running
  const totalSpend = summary?.totals?.total_spend ?? 0

  const hasRaw = raw > 0
  const hasNormalized = normalized > 0
  const hasCategorized = categorized > 0
  const allReviewed = hasCategorized && reviewCount === 0

  const nextAction = getNextAction({ pipelineRunning, hasRaw, hasNormalized, hasCategorized, reviewCount, allReviewed })

  const readinessSteps: { label: string; done: boolean; detail?: string }[] = [
    { label: 'Statements loaded', done: hasRaw, detail: hasRaw ? `${raw.toLocaleString()} rows` : undefined },
    { label: 'Transactions normalized', done: hasNormalized, detail: hasNormalized ? `${normalized.toLocaleString()}` : undefined },
    { label: 'Transactions categorized', done: hasCategorized, detail: hasCategorized ? `${categorized.toLocaleString()}` : undefined },
    {
      label: 'All items reviewed',
      done: allReviewed,
      detail: reviewCount > 0 ? `${reviewCount} remaining` : undefined,
    },
  ]

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Home</h1>

      {/* Next Action — hero card */}
      <div className={`rounded-xl p-6 border ${nextAction.borderColor} ${nextAction.bgColor}`}>
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Next step</div>
        <div className="text-xl font-semibold text-gray-100 mb-1">{nextAction.title}</div>
        {nextAction.subtitle && (
          <div className="text-sm text-gray-400 mb-4">{nextAction.subtitle}</div>
        )}
        {nextAction.route && !pipelineRunning && (
          <button
            onClick={() => navigate(nextAction.route!)}
            className={`px-5 py-2.5 rounded-lg font-medium text-sm transition-colors ${nextAction.buttonClass}`}
          >
            {nextAction.buttonLabel}
          </button>
        )}
        {pipelineRunning && (
          <div className="flex items-center gap-2 text-yellow-400 text-sm mt-2">
            <span className="animate-pulse">&#9679;</span> Pipeline is running&hellip;
          </div>
        )}
      </div>

      {/* Export Readiness Checklist */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-3">Export readiness</div>
        <div className="space-y-3">
          {readinessSteps.map((step) => (
            <div key={step.label} className="flex items-center gap-3">
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  step.done ? 'bg-green-500/20 text-green-400' : 'bg-gray-800 text-gray-600'
                }`}
              >
                {step.done ? '\u2713' : '\u2013'}
              </div>
              <span className="flex-1 text-sm text-gray-300">{step.label}</span>
              {step.detail && (
                <span className={`text-sm font-mono ${step.done ? 'text-gray-500' : 'text-yellow-400'}`}>
                  {step.detail}
                </span>
              )}
            </div>
          ))}
        </div>
        {allReviewed && (
          <button
            onClick={() => navigate('/export')}
            className="mt-4 w-full bg-green-600 hover:bg-green-500 text-white py-2.5 rounded-lg font-medium text-sm transition-colors"
          >
            Export Results
          </button>
        )}
      </div>

      {/* Key Numbers */}
      {hasCategorized && (
        <div className="grid grid-cols-2 gap-3">
          <NumberCard
            label="Pending review"
            value={reviewCount.toString()}
            accent={reviewCount > 0 ? 'text-yellow-400' : 'text-green-400'}
          />
          <NumberCard label="Total deductible" value={formatCurrency(totalDeductible)} accent="text-green-400" />
          {totalSpend > 0 && (
            <>
              <NumberCard label="Total spend" value={formatCurrency(totalSpend)} />
              <NumberCard
                label="Deduction rate"
                value={`${Math.round((totalDeductible / totalSpend) * 100)}%`}
                accent="text-blue-400"
              />
            </>
          )}
        </div>
      )}

      {/* Institution Summary — compact */}
      {status.by_institution.length > 0 && hasCategorized && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-3">By institution</div>
          <div className="space-y-2">
            {status.by_institution.map((inst) => (
              <div key={inst.institution} className="flex items-center justify-between text-sm">
                <span className="text-gray-300 font-medium">{inst.institution}</span>
                <div className="flex gap-4 text-gray-500 text-xs">
                  <span>{inst.categorized_count} categorized</span>
                  {inst.review_count > 0 && (
                    <span className="text-yellow-400">{inst.review_count} to review</span>
                  )}
                  <span className="text-green-400">{inst.business_count} business</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Spend Breakdown Pie Chart */}
      {hasCategorized && totalSpend > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-3">Spend breakdown</div>
          <SpendPieChart
            deductible={totalDeductible}
            personal={summary?.totals?.total_personal ?? 0}
            totalSpend={totalSpend}
          />
        </div>
      )}

      {/* Category Summary Table */}
      {summary?.by_category && summary.by_category.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-3">By category</div>
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 text-xs text-gray-500 uppercase tracking-wide pb-1 border-b border-gray-800">
              <span>Category</span>
              <span className="text-right">Count</span>
              <span className="text-right">Spent</span>
              <span className="text-right">Deductible</span>
            </div>
            {summary.by_category.map((cat) => (
              <div
                key={cat.category}
                className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 text-sm items-center"
              >
                <span className="text-gray-300 truncate">{cat.category}</span>
                <span className="text-gray-500 text-right tabular-nums">{cat.transaction_count}</span>
                <span className="text-gray-400 text-right tabular-nums">{formatCurrency(cat.total_original)}</span>
                <span className="text-green-400 text-right tabular-nums">{formatCurrency(cat.total_deductible)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function NumberCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ?? 'text-gray-100'}`}>{value}</div>
    </div>
  )
}

const PIE_COLORS = ['#22c55e', '#6b7280', '#eab308']

function SpendPieChart({ deductible, personal, totalSpend }: { deductible: number; personal: number; totalSpend: number }) {
  const uncategorized = Math.max(0, totalSpend - deductible - personal)
  const data = [
    { name: 'Deductible', value: deductible },
    { name: 'Personal', value: personal },
    ...(uncategorized > 0 ? [{ name: 'Uncategorized', value: uncategorized }] : []),
  ].filter((d) => d.value > 0)

  if (data.length === 0) return null

  return (
    <div className="flex flex-col sm:flex-row items-center gap-4">
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2}>
            {data.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(val: number) => formatCurrency(val)}
            contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 13 }}
            itemStyle={{ color: '#d1d5db' }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex sm:flex-col gap-3 text-sm">
        {data.map((d, i) => (
          <div key={d.name} className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
            <span className="text-gray-400">{d.name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
