import { useStatus } from '../hooks/useApi'

export default function StatusBar() {
  const { data: status, isLoading } = useStatus()

  if (isLoading || !status) {
    return (
      <div className="bg-gray-900 text-gray-400 text-sm px-4 py-2 text-center">
        Loading status...
      </div>
    )
  }

  return (
    <div className="bg-gray-900 text-gray-300 text-sm px-4 py-2 flex items-center justify-between">
      <span>
        {status.review_count > 0 ? (
          <>
            <span className="inline-flex items-center justify-center bg-yellow-500 text-gray-900 font-bold rounded-full w-6 h-6 text-xs mr-1">
              {status.review_count}
            </span>
            pending review
          </>
        ) : (
          'No items pending review'
        )}
      </span>
      <span className="font-medium text-green-400">
        ${Number(status.total_deductible).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} deductible
      </span>
    </div>
  )
}
