import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useSwipe } from '../hooks/useSwipe'
import TransactionCard from './TransactionCard'
import PartialAmountModal from './PartialAmountModal'
import type { ReviewTransaction, ReviewDecision, BatchReviewDecision } from '../types'

interface SwipeContainerProps {
  transactions: ReviewTransaction[]
  categories: string[]
  onReview: (transactionId: string, decision: ReviewDecision) => Promise<unknown>
  onBatchReview: (decision: BatchReviewDecision) => Promise<unknown>
  onSkip: () => void
}

type FlyDirection = 'right' | 'left' | 'up' | 'down'
type ReviewStatus = ReviewDecision['deductible_status']

type RetryAction = SingleReviewAction | BatchReviewAction

interface StatusBanner {
  tone: 'info' | 'success' | 'error'
  title: string
  detail: string
}

interface SingleReviewAction {
  kind: 'single'
  transactionId: string
  merchant: string
  category: string
  status: ReviewStatus
  amount: number
  notes: string
  direction: Exclude<FlyDirection, 'down'>
}

interface BatchReviewAction {
  kind: 'batch'
  merchant: string
  direction: Exclude<FlyDirection, 'down'>
  decision: BatchReviewDecision
  removeIds: string[]
}

function suggestKeyword(merchant: string): string {
  const clean = merchant.replace(/[^a-zA-Z0-9\s-]/g, ' ')
  const tokens = clean.split(/\s+/).filter((token) => token.length >= 3)
  return tokens.length > 0 ? tokens[0].toLowerCase() : merchant.toLowerCase().trim().slice(0, 20)
}

function getBannerClasses(tone: StatusBanner['tone']): string {
  if (tone === 'error') {
    return 'border-red-800 bg-red-900/30 text-red-100'
  }
  if (tone === 'success') {
    return 'border-green-800 bg-green-900/25 text-green-100'
  }
  return 'border-blue-800 bg-blue-900/20 text-blue-100'
}

function getErrorDetail(error: unknown): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message.trim()
  }
  return 'The request did not complete.'
}

function getStatusLabel(status: ReviewStatus): string {
  if (status === 'full') return 'full deduction'
  if (status === 'partial') return 'partial deduction'
  return 'personal'
}

export default function SwipeContainer({
  transactions,
  categories,
  onReview,
  onBatchReview,
  onSkip,
}: SwipeContainerProps) {
  const [queueIds, setQueueIds] = useState<string[]>(() =>
    transactions.map((transaction) => transaction.transaction_id)
  )
  const [selectedCategory, setSelectedCategory] = useState('')
  const [showPartialModal, setShowPartialModal] = useState(false)
  const [flyDirection, setFlyDirection] = useState<FlyDirection | null>(null)
  const [isAnimating, setIsAnimating] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [saveRule, setSaveRule] = useState(false)
  const [ruleKeyword, setRuleKeyword] = useState('')
  const [resolvedCount, setResolvedCount] = useState(0)
  const [banner, setBanner] = useState<StatusBanner | null>(null)
  const [lastSkippedId, setLastSkippedId] = useState<string | null>(null)

  const retryActionRef = useRef<RetryAction | null>(null)
  const pendingRemovalIdsRef = useRef(new Set<string>())
  const animationTimeoutRef = useRef<number | null>(null)

  const transactionMap = useMemo(
    () => new Map(transactions.map((transaction) => [transaction.transaction_id, transaction])),
    [transactions]
  )

  const queue = useMemo(
    () =>
      queueIds
        .map((transactionId) => transactionMap.get(transactionId))
        .filter((transaction): transaction is ReviewTransaction => Boolean(transaction)),
    [queueIds, transactionMap]
  )

  const currentTransaction = queue[0]
  const isBusy = isAnimating || isSubmitting
  const sessionTotal = resolvedCount + queue.length
  const progressWidth = sessionTotal === 0 ? 100 : (resolvedCount / sessionTotal) * 100

  const batchCount = useMemo(() => {
    if (!currentTransaction) return 0
    return queue.filter(
      (transaction) =>
        transaction.merchant_normalized === currentTransaction.merchant_normalized
    ).length
  }, [queue, currentTransaction])

  useEffect(() => {
    if (!currentTransaction) return
    setSelectedCategory(currentTransaction.category || '')
    setRuleKeyword(suggestKeyword(currentTransaction.merchant_normalized))
  }, [currentTransaction])

  useEffect(() => {
    if (isSubmitting || isAnimating) return

    const incomingIds = transactions.map((transaction) => transaction.transaction_id)
    const incomingIdSet = new Set(incomingIds)

    for (const pendingId of Array.from(pendingRemovalIdsRef.current)) {
      if (!incomingIdSet.has(pendingId)) {
        pendingRemovalIdsRef.current.delete(pendingId)
      }
    }

    setQueueIds((previousIds) => {
      const keptIds = previousIds.filter((transactionId) => incomingIdSet.has(transactionId))
      const keptIdSet = new Set(keptIds)
      const appendedIds = incomingIds.filter(
        (transactionId) =>
          !keptIdSet.has(transactionId) &&
          !pendingRemovalIdsRef.current.has(transactionId)
      )
      return [...keptIds, ...appendedIds]
    })
  }, [transactions, isSubmitting, isAnimating])

  useEffect(
    () => () => {
      if (animationTimeoutRef.current !== null) {
        window.clearTimeout(animationTimeoutRef.current)
      }
    },
    []
  )

  const animateAndCommit = useCallback((direction: FlyDirection, commit: () => void) => {
    if (animationTimeoutRef.current !== null) {
      window.clearTimeout(animationTimeoutRef.current)
    }

    setFlyDirection(direction)
    setIsAnimating(true)
    animationTimeoutRef.current = window.setTimeout(() => {
      commit()
      setFlyDirection(null)
      setIsAnimating(false)
      animationTimeoutRef.current = null
    }, 300)
  }, [])

  const runSingleReview = useCallback(
    async (action: SingleReviewAction) => {
      retryActionRef.current = action
      setIsSubmitting(true)
      setLastSkippedId(null)
      setBanner({
        tone: 'info',
        title: 'Saving review...',
        detail: `Waiting for confirmation before moving ${action.merchant}.`,
      })

      try {
        await onReview(action.transactionId, {
          category: action.category,
          deductible_status: action.status,
          deductible_amount: action.amount,
          notes: action.notes,
        })

        retryActionRef.current = null
        pendingRemovalIdsRef.current.add(action.transactionId)

        animateAndCommit(action.direction, () => {
          setQueueIds((previousIds) =>
            previousIds.filter((transactionId) => transactionId !== action.transactionId)
          )
          setResolvedCount((previousCount) => previousCount + 1)
          setBanner({
            tone: 'success',
            title: 'Review saved',
            detail: `${action.merchant} was marked ${getStatusLabel(action.status)}.`,
          })
          setIsSubmitting(false)
        })
      } catch (error) {
        setIsSubmitting(false)
        setBanner({
          tone: 'error',
          title: 'Could not save review',
          detail: `${getErrorDetail(error)} The card stayed in place so you can retry or adjust the decision.`,
        })
      }
    },
    [animateAndCommit, onReview]
  )

  const runBatchReview = useCallback(
    async (action: BatchReviewAction) => {
      retryActionRef.current = action
      setIsSubmitting(true)
      setLastSkippedId(null)
      setBanner({
        tone: 'info',
        title: 'Applying matching reviews...',
        detail: `Waiting for confirmation before clearing ${action.merchant} from the queue.`,
      })

      try {
        const response = await onBatchReview(action.decision)

        retryActionRef.current = null
        for (const transactionId of action.removeIds) {
          pendingRemovalIdsRef.current.add(transactionId)
        }

        const responseCount =
          typeof response === 'object' &&
          response !== null &&
          'count' in response &&
          typeof (response as { count?: number }).count === 'number'
            ? (response as { count: number }).count
            : action.removeIds.length

        animateAndCommit(action.direction, () => {
          const removalSet = new Set(action.removeIds)
          setQueueIds((previousIds) =>
            previousIds.filter((transactionId) => !removalSet.has(transactionId))
          )
          setResolvedCount((previousCount) => previousCount + responseCount)
          setBanner({
            tone: 'success',
            title: `Applied to ${responseCount} transaction${responseCount === 1 ? '' : 's'}`,
            detail: `All pending ${action.merchant} entries were updated together.`,
          })
          setIsSubmitting(false)
        })
      } catch (error) {
        setIsSubmitting(false)
        setBanner({
          tone: 'error',
          title: 'Could not apply the batch review',
          detail: `${getErrorDetail(error)} The current card stayed in place so you can retry safely.`,
        })
      }
    },
    [animateAndCommit, onBatchReview]
  )

  const runResolvedAction = useCallback(
    (status: ReviewStatus, amount: number, notes: string, direction: Exclude<FlyDirection, 'down'>) => {
      if (!currentTransaction || isBusy) return

      const category = selectedCategory || currentTransaction.category || 'Other expenses'

      if (saveRule) {
        const merchant = currentTransaction.merchant_normalized
        const removeIds = queue
          .filter((transaction) => transaction.merchant_normalized === merchant)
          .map((transaction) => transaction.transaction_id)

        const batchAction: BatchReviewAction = {
          kind: 'batch',
          merchant,
          direction,
          removeIds,
          decision: {
            merchant_normalized: merchant,
            category,
            deductible_status: status,
            notes: notes || 'batch + rule via swipe UI',
            save_rule: true,
            rule_keyword: ruleKeyword.trim() || suggestKeyword(merchant),
          },
        }

        void runBatchReview(batchAction)
        return
      }

      const singleAction: SingleReviewAction = {
        kind: 'single',
        transactionId: currentTransaction.transaction_id,
        merchant: currentTransaction.merchant_normalized,
        category,
        status,
        amount,
        notes,
        direction,
      }

      void runSingleReview(singleAction)
    },
    [
      currentTransaction,
      isBusy,
      queue,
      ruleKeyword,
      runBatchReview,
      runSingleReview,
      saveRule,
      selectedCategory,
    ]
  )

  const handleSwipeRight = useCallback(() => {
    if (!currentTransaction || isBusy) return
    runResolvedAction('full', Number(currentTransaction.original_amount) || 0, '', 'right')
  }, [currentTransaction, isBusy, runResolvedAction])

  const handleSwipeLeft = useCallback(() => {
    if (!currentTransaction || isBusy) return
    runResolvedAction('personal', 0, '', 'left')
  }, [currentTransaction, isBusy, runResolvedAction])

  const handleSwipeUp = useCallback(() => {
    if (!currentTransaction || isBusy) return
    setShowPartialModal(true)
  }, [currentTransaction, isBusy])

  const handleSwipeDown = useCallback(() => {
    if (!currentTransaction || isBusy) return
    if (queue.length <= 1) {
      setBanner({
        tone: 'info',
        title: 'Nothing else to skip to',
        detail: 'This is the only remaining transaction in the queue.',
      })
      return
    }

    const skippedTransactionId = currentTransaction.transaction_id
    const skippedMerchant = currentTransaction.merchant_normalized

    retryActionRef.current = null
    onSkip()
    setLastSkippedId(skippedTransactionId)
    setBanner({
      tone: 'info',
      title: 'Skipped for now',
      detail: `${skippedMerchant} moved to the end of the queue. Use Undo skip if you want it back on top.`,
    })

    animateAndCommit('down', () => {
      setQueueIds((previousIds) => {
        if (previousIds.length <= 1) return previousIds
        const [firstId, ...restIds] = previousIds
        return [...restIds, firstId]
      })
    })
  }, [currentTransaction, isBusy, onSkip, queue.length, animateAndCommit])

  const handlePartialConfirm = useCallback(
    (amount: number, notes: string) => {
      setShowPartialModal(false)
      runResolvedAction('partial', amount, notes, 'up')
    },
    [runResolvedAction]
  )

  const handlePartialCancel = useCallback(() => {
    if (isSubmitting) return
    setShowPartialModal(false)
  }, [isSubmitting])

  const handleUndoSkip = useCallback(() => {
    if (!lastSkippedId || isBusy) return

    const skippedTransaction = transactionMap.get(lastSkippedId)

    setQueueIds((previousIds) => {
      const skippedIndex = previousIds.indexOf(lastSkippedId)
      if (skippedIndex <= 0) return previousIds
      const nextIds = [...previousIds]
      nextIds.splice(skippedIndex, 1)
      nextIds.unshift(lastSkippedId)
      return nextIds
    })

    setLastSkippedId(null)
    setBanner({
      tone: 'success',
      title: 'Skip undone',
      detail: skippedTransaction
        ? `${skippedTransaction.merchant_normalized} is back at the top of the queue.`
        : 'The skipped transaction is back at the top of the queue.',
    })
  }, [isBusy, lastSkippedId, transactionMap])

  const handleRetry = useCallback(() => {
    if (isBusy || !retryActionRef.current) return
    const retryAction = retryActionRef.current
    if (retryAction.kind === 'single') {
      void runSingleReview(retryAction)
      return
    }
    void runBatchReview(retryAction)
  }, [isBusy, runBatchReview, runSingleReview])

  const handleBatchApply = useCallback(() => {
    if (!currentTransaction || isBusy) return

    const merchant = currentTransaction.merchant_normalized
    const removeIds = queue
      .filter((transaction) => transaction.merchant_normalized === merchant)
      .map((transaction) => transaction.transaction_id)

    const action: BatchReviewAction = {
      kind: 'batch',
      merchant,
      direction: 'right',
      removeIds,
      decision: {
        merchant_normalized: merchant,
        category: selectedCategory || currentTransaction.category || 'Other expenses',
        deductible_status: 'full',
        notes: 'batch applied via swipe UI',
      },
    }

    void runBatchReview(action)
  }, [currentTransaction, isBusy, queue, runBatchReview, selectedCategory])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (showPartialModal) return

      switch (event.key) {
        case 'ArrowRight':
          event.preventDefault()
          handleSwipeRight()
          break
        case 'ArrowLeft':
          event.preventDefault()
          handleSwipeLeft()
          break
        case 'ArrowUp':
          event.preventDefault()
          handleSwipeUp()
          break
        case 'ArrowDown':
          event.preventDefault()
          handleSwipeDown()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showPartialModal, handleSwipeRight, handleSwipeLeft, handleSwipeUp, handleSwipeDown])

  function getFlyStyle(): React.CSSProperties {
    if (!flyDirection) return {}
    const flyMap: Record<FlyDirection, string> = {
      right: 'translateX(1000px) rotate(30deg)',
      left: 'translateX(-1000px) rotate(-30deg)',
      up: 'translateY(-1000px)',
      down: 'translateY(1000px)',
    }
    return {
      transform: flyMap[flyDirection],
      opacity: 0,
      transition: 'transform 300ms ease-out, opacity 300ms ease-out',
    }
  }

  const { state: swipeState, handlers } = useSwipe({
    onSwipeRight: handleSwipeRight,
    onSwipeLeft: handleSwipeLeft,
    onSwipeUp: handleSwipeUp,
    onSwipeDown: handleSwipeDown,
    threshold: 100,
    velocityThreshold: 0.5,
  })

  if (!currentTransaction) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <div className="text-5xl mb-4">&#10003;</div>
        <h2 className="text-2xl font-bold text-gray-100 mb-2">All caught up!</h2>
        <p className="text-gray-400">
          You've reviewed all {resolvedCount} transaction{resolvedCount === 1 ? '' : 's'} in this session.
        </p>
      </div>
    )
  }

  const visibleCards = queue.slice(0, 3).map((transaction, index) => ({
    transaction,
    offset: index,
  }))

  return (
    <div className="flex-1 flex flex-col">
      <div className="px-4 py-2">
        <div className="flex items-center justify-between text-sm text-gray-400 mb-1 gap-3">
          <span>
            {resolvedCount} reviewed in this session, {queue.length} remaining on screen
          </span>
          {lastSkippedId && !isBusy && (
            <button
              onClick={handleUndoSkip}
              className="text-blue-400 hover:text-blue-300 transition-colors text-sm"
            >
              Undo skip
            </button>
          )}
        </div>
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300"
            style={{ width: `${progressWidth}%` }}
          />
        </div>
      </div>

      {banner && (
        <div className="px-4 pb-2">
          <div className={`rounded-xl border px-4 py-3 ${getBannerClasses(banner.tone)}`}>
            <div className="flex items-start gap-3">
              {isSubmitting ? (
                <span className="mt-0.5 inline-block h-4 w-4 shrink-0 rounded-full border-2 border-current border-t-transparent animate-spin" />
              ) : (
                <span className="mt-0.5 text-sm font-bold">
                  {banner.tone === 'error' ? '!' : banner.tone === 'success' ? 'OK' : 'i'}
                </span>
              )}
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{banner.title}</p>
                <p className="text-sm opacity-90 mt-1">{banner.detail}</p>
              </div>
            </div>
            {!isSubmitting && (
              <div className="mt-3 flex flex-wrap gap-2">
                {banner.tone === 'error' && retryActionRef.current && (
                  <button
                    onClick={handleRetry}
                    disabled={isBusy}
                    className="px-3 py-1.5 rounded-lg bg-red-200 text-red-950 hover:bg-red-100 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Retry save
                  </button>
                )}
                <button
                  onClick={() => setBanner(null)}
                  className="px-3 py-1.5 rounded-lg bg-black/20 hover:bg-black/30 transition-colors"
                >
                  Dismiss
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <div
        className="flex-1 flex items-center justify-center px-4 py-4 relative"
        style={{ touchAction: 'none' }}
      >
        <div className="relative w-full max-w-sm" style={{ height: '480px' }}>
          {visibleCards
            .slice()
            .reverse()
            .map(({ transaction, offset }) => {
              const isTop = offset === 0
              const scale = 1 - offset * 0.05
              const translateY = offset * 12

              const baseStyle: React.CSSProperties = {
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                transform: `scale(${scale}) translateY(${translateY}px)`,
                zIndex: 3 - offset,
                transition:
                  isTop && !isAnimating
                    ? 'none'
                    : 'transform 300ms ease-out, opacity 300ms ease-out',
              }

              if (isTop && swipeState.isDragging && !isBusy) {
                baseStyle.transform = `translateX(${swipeState.x}px) translateY(${swipeState.y}px) rotate(${swipeState.x * 0.1}deg)`
                baseStyle.transition = 'none'
              }

              if (isTop && flyDirection) {
                Object.assign(baseStyle, getFlyStyle())
              }

              return (
                <div
                  key={transaction.transaction_id}
                  style={baseStyle}
                  {...(isTop && !isBusy ? handlers : {})}
                >
                  <TransactionCard
                    transaction={transaction}
                    isTop={isTop}
                    swipeState={isTop ? swipeState : undefined}
                    categories={categories}
                    selectedCategory={isTop ? selectedCategory : transaction.category || ''}
                    onCategoryChange={isTop ? setSelectedCategory : () => {}}
                    disabled={isTop ? isBusy : true}
                  />
                </div>
              )
            })}
        </div>
      </div>

      <div className="px-4 pb-2 space-y-2">
        <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3 border border-gray-700">
          <button
            onClick={() => setSaveRule(!saveRule)}
            disabled={isBusy}
            className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
              saveRule ? 'bg-purple-600' : 'bg-gray-600'
            }`}
          >
            <span
              className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform mt-0.5 ${
                saveRule ? 'translate-x-5.5 ml-0.5' : 'translate-x-0.5'
              }`}
            />
          </button>
          <div className="flex-1 min-w-0">
            <span className="text-sm text-gray-200">Apply to similar and save rule</span>
            {saveRule && (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-gray-400">Keyword:</span>
                <input
                  value={ruleKeyword}
                  onChange={(event) => setRuleKeyword(event.target.value)}
                  disabled={isBusy}
                  className="flex-1 bg-gray-900 border border-gray-600 text-gray-200 rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </div>
            )}
          </div>
        </div>

        {!saveRule && batchCount > 1 && (
          <button
            onClick={handleBatchApply}
            disabled={isBusy}
            className="w-full py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            Apply to all {batchCount} from {currentTransaction.merchant_normalized}
          </button>
        )}
      </div>

      <div className="grid grid-cols-4 gap-2 px-4 pb-4">
        <button
          onClick={handleSwipeLeft}
          disabled={isBusy}
          className="py-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-200 rounded-lg text-sm font-medium transition-colors"
        >
          Personal
        </button>
        <button
          onClick={handleSwipeUp}
          disabled={isBusy}
          className="py-3 bg-yellow-700 hover:bg-yellow-600 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Partial
        </button>
        <button
          onClick={handleSwipeDown}
          disabled={isBusy}
          className="py-3 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Skip
        </button>
        <button
          onClick={handleSwipeRight}
          disabled={isBusy}
          className="py-3 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Full
        </button>
      </div>

      <PartialAmountModal
        isOpen={showPartialModal && Boolean(currentTransaction)}
        transaction={currentTransaction}
        category={selectedCategory || currentTransaction.category || 'Other expenses'}
        onConfirm={handlePartialConfirm}
        onCancel={handlePartialCancel}
        isSubmitting={isSubmitting}
      />
    </div>
  )
}
