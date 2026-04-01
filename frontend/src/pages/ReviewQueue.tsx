import { useReviewQueue, useCategories, useSubmitReview, useBatchReview, useStatus } from '../hooks/useApi'
import SwipeContainer from '../components/SwipeContainer'
import type { ReviewDecision, BatchReviewDecision } from '../types'

export default function ReviewQueue() {
  const { data, isLoading, error } = useReviewQueue()
  const { data: categories } = useCategories()
  const { data: status } = useStatus()
  const submitReview = useSubmitReview()
  const batchReview = useBatchReview()
  const pipelineRunning = status?.pipeline_running ?? false

  const handleReview = async (transactionId: string, decision: ReviewDecision) =>
    submitReview.mutateAsync({ id: transactionId, decision })

  const handleBatchReview = async (decision: BatchReviewDecision) =>
    batchReview.mutateAsync(decision)

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-gray-400 text-sm">Loading review queue...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-4 max-w-sm text-center">
          <h2 className="text-red-300 font-bold mb-1">Error loading queue</h2>
          <p className="text-red-400 text-sm">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    )
  }

  if (pipelineRunning) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <div className="mb-4 rounded-lg border border-yellow-700 bg-yellow-900/20 p-4 max-w-sm">
          <div className="flex items-center justify-center gap-2 text-yellow-300 mb-2">
            <span className="inline-block w-5 h-5 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
            <span className="font-bold">Pipeline Running</span>
          </div>
          <p className="text-yellow-400 text-sm">
            Reviews are disabled while a pipeline step is running.
          </p>
        </div>
      </div>
    )
  }

  if (!data?.transactions.length) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <div className="text-5xl mb-4">&#10003;</div>
        <h2 className="text-2xl font-bold text-gray-100 mb-2">All caught up!</h2>
        <p className="text-gray-400">No transactions need review right now.</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <header className="px-4 pt-4 pb-2">
        <h1 className="text-xl font-bold text-gray-100">
          Review Queue
          <span className="text-gray-400 font-normal text-base ml-2">
            {data.total} remaining
          </span>
        </h1>
      </header>
      <SwipeContainer
        transactions={data.transactions}
        categories={categories || []}
        onReview={handleReview}
        onBatchReview={handleBatchReview}
        onSkip={() => {}}
      />
    </div>
  )
}
