import type { KeywordRule, DeductionRule } from '../../types'

export function statusColor(status: string): string {
  switch (status) {
    case 'full':
      return 'text-green-400'
    case 'partial':
      return 'text-yellow-400'
    case 'personal':
      return 'text-gray-400'
    default:
      return 'text-gray-300'
  }
}

export function formatMethod(rule: DeductionRule): string {
  switch (rule.method) {
    case 'fixed_monthly':
      return `$${rule.amount ?? 0}/mo`
    case 'percentage':
      return `${rule.percentage ?? 0}%`
    case 'personal':
      return '0%'
    case 'full':
      return '100%'
    default:
      return rule.method
  }
}

export function formatKeywordConfidence(rule: KeywordRule): string {
  return `${Math.round(rule.confidence * 100)}%`
}

export const ACTION_STYLES: Record<string, string> = {
  add: 'bg-green-900/50 text-green-400 border-green-700',
  update: 'bg-blue-900/50 text-blue-400 border-blue-700',
  delete: 'bg-red-900/50 text-red-400 border-red-700',
  bulk_save: 'bg-yellow-900/50 text-yellow-400 border-yellow-700',
}
