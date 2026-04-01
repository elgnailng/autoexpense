import type {
  Transaction,
  ReviewTransaction,
  ReviewDecision,
  BatchReviewDecision,
  PipelineStatus,
  CategorySummary,
  PipelineResult,
  KeywordRule,
  DeductionRule,
  ConfigChangeEntry,
  LLMProgressEvent,
  LLMConfig,
  LLMProgressPoll,
  ResetResult,
  AccountantUser,
} from '../types'

const API_BASE = '/api'

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('Not authenticated')
  }
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || res.statusText)
  }
  return res.json()
}

export const api = {
  getStatus: () => fetchApi<PipelineStatus>('/status'),

  getTransactions: (params?: URLSearchParams) =>
    fetchApi<{ transactions: Transaction[]; total: number; total_amount: number }>(
      `/transactions${params ? '?' + params : ''}`
    ),

  getTransaction: (id: string) => fetchApi<Transaction>(`/transactions/${id}`),

  getCategories: () => fetchApi<string[]>('/categories'),

  getReviewQueue: () =>
    fetchApi<{ transactions: ReviewTransaction[]; total: number }>('/review-queue'),

  getSummary: () =>
    fetchApi<{ totals: Record<string, number>; by_category: CategorySummary[] }>('/summary'),

  submitReview: (id: string, decision: ReviewDecision) =>
    fetchApi<{ success: boolean }>(`/transactions/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(decision),
    }),

  batchReview: (decision: BatchReviewDecision) =>
    fetchApi<{ success: boolean; count: number }>('/transactions/batch-review', {
      method: 'POST',
      body: JSON.stringify(decision),
    }),

  runPipeline: (step: string, options?: { use_llm?: boolean; provider?: string; model?: string; force?: boolean }) =>
    fetchApi<PipelineResult>(`/pipeline/${step}`, {
      method: 'POST',
      body: options ? JSON.stringify(options) : undefined,
    }),

  runLLMCategorize: (options?: {
    provider?: string
    model?: string
    apiKey?: string
    dryRun?: boolean
    force?: boolean
  }) =>
    fetchApi<PipelineResult>('/pipeline/llm-categorize', {
      method: 'POST',
      body: JSON.stringify({
        provider: options?.provider,
        model: options?.model,
        api_key: options?.apiKey,
        dry_run: options?.dryRun ?? false,
        force: options?.force ?? false,
      }),
    }),

  // Config — keyword rules
  getKeywordRules: () => fetchApi<KeywordRule[]>('/config/rules'),
  addKeywordRule: (rule: Omit<KeywordRule, 'index'>) =>
    fetchApi<{ success: boolean; index: number }>('/config/rules', {
      method: 'POST',
      body: JSON.stringify(rule),
    }),
  updateKeywordRule: (index: number, rule: Omit<KeywordRule, 'index'>) =>
    fetchApi<{ success: boolean }>(`/config/rules/${index}`, {
      method: 'PUT',
      body: JSON.stringify(rule),
    }),
  deleteKeywordRule: (index: number) =>
    fetchApi<{ success: boolean }>(`/config/rules/${index}`, { method: 'DELETE' }),

  // Config — deduction rules
  getDeductionRules: () => fetchApi<DeductionRule[]>('/config/deduction-rules'),
  addDeductionRule: (rule: Omit<DeductionRule, 'index'>) =>
    fetchApi<{ success: boolean; index: number }>('/config/deduction-rules', {
      method: 'POST',
      body: JSON.stringify(rule),
    }),
  updateDeductionRule: (index: number, rule: Omit<DeductionRule, 'index'>) =>
    fetchApi<{ success: boolean }>(`/config/deduction-rules/${index}`, {
      method: 'PUT',
      body: JSON.stringify(rule),
    }),
  deleteDeductionRule: (index: number) =>
    fetchApi<{ success: boolean }>(`/config/deduction-rules/${index}`, { method: 'DELETE' }),

  // Config — change history
  getConfigHistory: (limit = 50, configFile?: string) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (configFile) params.set('config_file', configFile)
    return fetchApi<ConfigChangeEntry[]>(`/config/history?${params}`)
  },

  // LLM config
  getLLMConfig: () => fetchApi<LLMConfig>('/pipeline/llm-config'),

  // LLM progress polling (for clients that didn't start the stream)
  getLLMProgress: () => fetchApi<LLMProgressPoll>('/pipeline/llm-progress'),

  // LLM categorization — SSE stream (POST)
  streamLLMCategorize: (
    onEvent: (event: LLMProgressEvent) => void,
    options?: { provider?: string; model?: string; apiKey?: string; dryRun?: boolean; force?: boolean },
  ): (() => void) => {
    const body = JSON.stringify({
      provider: options?.provider,
      model: options?.model,
      api_key: options?.apiKey,
      dry_run: options?.dryRun ?? false,
      force: options?.force ?? false,
    })

    const controller = new AbortController()
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/pipeline/llm-categorize/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body,
          signal: controller.signal,
          credentials: 'include',
        })
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          onEvent({ type: 'error', message: err.detail || res.statusText })
          return
        }
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6)) as LLMProgressEvent
                onEvent(event)
              } catch { /* skip malformed */ }
            }
          }
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === 'AbortError')) {
          onEvent({ type: 'error', message: err instanceof Error ? err.message : 'Connection lost' })
        }
      }
    })()

    return () => controller.abort()
  },

  // Reset pipeline
  resetPipeline: (level: string) =>
    fetchApi<ResetResult>('/pipeline/reset', {
      method: 'POST',
      body: JSON.stringify({ level }),
    }),

  // Accountant management (owner only)
  getAccountants: () => fetchApi<AccountantUser[]>('/accountants'),
  inviteAccountant: (email: string, permission: string) =>
    fetchApi<AccountantUser>('/accountants', {
      method: 'POST',
      body: JSON.stringify({ email, permission }),
    }),
  updateAccountant: (email: string, permission: string) =>
    fetchApi<AccountantUser>(`/accountants/${encodeURIComponent(email)}`, {
      method: 'PUT',
      body: JSON.stringify({ permission }),
    }),
  revokeAccountant: (email: string) =>
    fetchApi<{ success: boolean }>(`/accountants/${encodeURIComponent(email)}`, {
      method: 'DELETE',
    }),

  // CSV export download
  downloadExport: async (fileType: string) => {
    const res = await fetch(`${API_BASE}/export/${fileType}`, { credentials: 'include' })
    if (res.status === 401) {
      window.location.href = '/login'
      throw new Error('Not authenticated')
    }
    if (!res.ok) throw new Error('Export failed')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${fileType}.csv`
    a.click()
    URL.revokeObjectURL(url)
  },

  // Create manual transaction
  createTransaction: (body: {
    merchant_name: string
    original_amount: number
    transaction_date: string
    category: string
    deductible_status: 'full' | 'partial' | 'personal'
    deductible_amount?: number
    institution?: string
    notes?: string
    is_credit?: boolean
  }) => fetchApi<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(body) }),

  // Flag transaction (accountant with view_flag)
  flagTransaction: (id: string, reason: string) =>
    fetchApi<{ success: boolean }>(`/transactions/${id}/flag`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  // Batch update (owner)
  batchUpdate: (body: { transaction_ids: string[]; category: string; deductible_status: string; notes?: string }) =>
    fetchApi<{ success: boolean; updated_count: number }>('/transactions/batch-update', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // Batch flag (accountant with view_flag)
  batchFlag: (body: { transaction_ids: string[]; reason: string }) =>
    fetchApi<{ success: boolean; flagged_count: number }>('/transactions/batch-flag', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
