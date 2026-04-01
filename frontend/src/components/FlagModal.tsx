import { useState, useEffect } from 'react'

interface FlagModalProps {
  merchantName: string
  onSubmit: (reason: string) => void
  onClose: () => void
  isPending?: boolean
}

export default function FlagModal({ merchantName, onSubmit, onClose, isPending }: FlagModalProps) {
  const [reason, setReason] = useState('')

  useEffect(() => {
    const original = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = original }
  }, [])

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div
        className="relative w-full max-w-sm mx-4 bg-gray-900 border border-gray-700 rounded-2xl p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold text-gray-100 mb-1">Flag for Review</h3>
        <p className="text-sm text-gray-400 mb-4">
          Flag <span className="text-gray-200 font-medium">{merchantName}</span> for the owner to re-review.
        </p>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why should this be reviewed? (required)"
          rows={3}
          maxLength={1000}
          className="w-full rounded-lg bg-gray-800 border border-gray-600 text-sm text-gray-200 px-3 py-2 focus:outline-none focus:border-blue-500 resize-none mb-4"
          autoFocus
        />
        <div className="flex gap-3">
          <button
            onClick={() => onSubmit(reason)}
            disabled={!reason.trim() || isPending}
            className="flex-1 rounded-lg py-2.5 text-sm font-medium bg-amber-600 hover:bg-amber-500 text-white disabled:bg-amber-900 disabled:text-amber-400 transition-colors"
          >
            {isPending ? 'Flagging...' : 'Flag'}
          </button>
          <button
            onClick={onClose}
            disabled={isPending}
            className="flex-1 rounded-lg py-2.5 text-sm font-medium bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
