import type { ReviewTransaction } from '../types'
import CategorySelect from './CategorySelect'

interface TransactionCardProps {
  transaction: ReviewTransaction
  style?: React.CSSProperties
  swipeState?: { x: number; y: number; direction: string | null }
  isTop?: boolean
  categories: string[]
  selectedCategory: string
  onCategoryChange: (category: string) => void
  disabled?: boolean
}

interface SwipeOverlayProps {
  direction: string | null
  x: number
  y: number
}

function SwipeOverlay({ direction, x, y }: SwipeOverlayProps) {
  if (!direction) return null

  const config: Record<string, { label: string; bg: string; text: string }> = {
    right: { label: 'FULL', bg: 'bg-green-500/80', text: 'text-white' },
    left: { label: 'PERSONAL', bg: 'bg-gray-500/80', text: 'text-white' },
    up: { label: 'PARTIAL', bg: 'bg-yellow-500/80', text: 'text-white' },
    down: { label: 'SKIP', bg: 'bg-blue-500/80', text: 'text-white' },
  }

  const c = config[direction]
  if (!c) return null

  const displacement = direction === 'right' || direction === 'left' ? Math.abs(x) : Math.abs(y)
  const opacity = Math.min(displacement / 150, 0.8)

  if (opacity < 0.05) return null

  return (
    <div
      className={`absolute inset-0 rounded-2xl ${c.bg} flex items-center justify-center pointer-events-none z-10`}
      style={{ opacity }}
    >
      <span className={`text-3xl font-bold ${c.text}`}>
        {c.label}
      </span>
    </div>
  )
}

export default function TransactionCard({
  transaction,
  style,
  swipeState,
  isTop = false,
  categories,
  selectedCategory,
  onCategoryChange,
  disabled = false,
}: TransactionCardProps) {
  const {
    transaction_date,
    institution,
    merchant_normalized,
    merchant_raw,
    description_raw,
    original_amount,
    confidence,
    category,
    rule_applied,
    notes,
  } = transaction

  void categories

  const displayDate = new Date(transaction_date).toLocaleDateString('en-CA', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  const showDescription =
    description_raw &&
    description_raw.toLowerCase() !== merchant_normalized.toLowerCase() &&
    description_raw.toLowerCase() !== merchant_raw.toLowerCase()

  const cardStyle: React.CSSProperties = { ...style }
  if (isTop && swipeState && swipeState.x !== 0) {
    cardStyle.transform = `${cardStyle.transform || ''} rotate(${swipeState.x * 0.1}deg)`.trim()
  }

  const amt = Number(original_amount) || 0
  const conf = Number(confidence) || 0
  const confidencePct = Math.round(conf * 100)

  return (
    <div
      className={`relative w-full max-w-sm bg-gray-800 rounded-2xl shadow-xl border overflow-hidden select-none ${
        disabled ? 'border-blue-500/60' : 'border-gray-700'
      }`}
      style={cardStyle}
    >
      {isTop && swipeState && (
        <SwipeOverlay direction={swipeState.direction} x={swipeState.x} y={swipeState.y} />
      )}

      <div className="p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between text-sm text-gray-400">
          <span>{displayDate}</span>
          <span className="px-2 py-0.5 bg-gray-700 rounded text-xs font-medium">
            {institution}
          </span>
        </div>

        <div>
          <h2 className="text-xl font-bold text-gray-100 leading-tight">
            {merchant_normalized}
          </h2>
          {showDescription && (
            <p className="text-sm text-gray-400 mt-0.5 truncate">{description_raw}</p>
          )}
        </div>

        <div className="flex items-end justify-between">
          <span className="text-2xl font-bold text-white">
            ${amt.toFixed(2)}
          </span>
          <span
            className={`text-sm font-medium ${
              confidencePct >= 85
                ? 'text-green-400'
                : confidencePct >= 50
                  ? 'text-yellow-400'
                  : 'text-red-400'
            }`}
          >
            conf: {confidencePct}%
          </span>
        </div>

        <div className="bg-gray-900/50 rounded-lg p-3 text-sm space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Suggested:</span>
            <span className="text-gray-200 font-medium">{category || 'None'}</span>
          </div>
          {rule_applied && (
            <div className="flex items-center gap-2">
              <span className="text-gray-400">Rule:</span>
              <span className="text-gray-300 font-mono text-xs">{rule_applied}</span>
            </div>
          )}
          {notes && (
            <p className="text-xs text-gray-400 italic mt-1">{notes}</p>
          )}
        </div>

        <div>
          <CategorySelect
            value={selectedCategory}
            onChange={onCategoryChange}
            className="w-full text-sm"
            disabled={disabled}
          />
        </div>

        <div className="grid grid-cols-3 text-center text-xs text-gray-500 pt-1">
          <span>&larr; Personal</span>
          <span>&uarr; Partial &darr; Skip</span>
          <span>Full &rarr;</span>
        </div>
      </div>
    </div>
  )
}
