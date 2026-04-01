import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ReviewDecision, BatchReviewDecision, KeywordRule, DeductionRule } from '../types'

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
    refetchInterval: 30_000,
  })
}

export function useTransactions(params?: URLSearchParams) {
  return useQuery({
    queryKey: ['transactions', params?.toString()],
    queryFn: () => api.getTransactions(params),
    placeholderData: (prev) => prev,
  })
}

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: api.getCategories,
    staleTime: 5 * 60_000,
  })
}

export function useReviewQueue() {
  return useQuery({
    queryKey: ['review-queue'],
    queryFn: api.getReviewQueue,
  })
}

export function useSummary() {
  return useQuery({
    queryKey: ['summary'],
    queryFn: api.getSummary,
  })
}

export function useSubmitReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: ReviewDecision }) =>
      api.submitReview(id, decision),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
    },
  })
}

export function useBatchReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (decision: BatchReviewDecision) => api.batchReview(decision),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
    },
  })
}

export function useRunPipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ step, options }: { step: string; options?: { use_llm?: boolean; provider?: string; model?: string } }) =>
      api.runPipeline(step, options),
    onSuccess: () => {
      queryClient.invalidateQueries()
    },
  })
}

// Config — keyword rules
export function useKeywordRules() {
  return useQuery({
    queryKey: ['keyword-rules'],
    queryFn: api.getKeywordRules,
  })
}

export function useAddKeywordRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (rule: Omit<KeywordRule, 'index'>) => api.addKeywordRule(rule),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['keyword-rules'] }),
  })
}

export function useUpdateKeywordRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ index, rule }: { index: number; rule: Omit<KeywordRule, 'index'> }) =>
      api.updateKeywordRule(index, rule),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['keyword-rules'] }),
  })
}

export function useDeleteKeywordRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (index: number) => api.deleteKeywordRule(index),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['keyword-rules'] }),
  })
}

// Config — deduction rules
export function useDeductionRules() {
  return useQuery({
    queryKey: ['deduction-rules'],
    queryFn: api.getDeductionRules,
  })
}

export function useAddDeductionRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (rule: Omit<DeductionRule, 'index'>) => api.addDeductionRule(rule),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['deduction-rules'] }),
  })
}

export function useUpdateDeductionRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ index, rule }: { index: number; rule: Omit<DeductionRule, 'index'> }) =>
      api.updateDeductionRule(index, rule),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['deduction-rules'] }),
  })
}

export function useDeleteDeductionRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (index: number) => api.deleteDeductionRule(index),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['deduction-rules'] }),
  })
}

// Config — change history
export function useConfigHistory(limit = 50, configFile?: string) {
  return useQuery({
    queryKey: ['config-history', limit, configFile],
    queryFn: () => api.getConfigHistory(limit, configFile),
  })
}

// LLM config
export function useLLMConfig() {
  return useQuery({
    queryKey: ['llm-config'],
    queryFn: api.getLLMConfig,
    staleTime: 60_000,
  })
}

// LLM progress polling (for clients that didn't start the SSE stream)
export function useLLMProgressPoll(enabled: boolean) {
  return useQuery({
    queryKey: ['llm-progress'],
    queryFn: api.getLLMProgress,
    refetchInterval: 2000,
    enabled,
  })
}

// Reset pipeline
export function useResetPipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (level: string) => api.resetPipeline(level),
    onSuccess: () => {
      queryClient.invalidateQueries()
    },
  })
}

// Accountant management
export function useAccountants() {
  return useQuery({
    queryKey: ['accountants'],
    queryFn: api.getAccountants,
  })
}

export function useInviteAccountant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ email, permission }: { email: string; permission: string }) =>
      api.inviteAccountant(email, permission),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accountants'] }),
  })
}

export function useUpdateAccountant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ email, permission }: { email: string; permission: string }) =>
      api.updateAccountant(email, permission),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accountants'] }),
  })
}

export function useRevokeAccountant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (email: string) => api.revokeAccountant(email),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accountants'] }),
  })
}

export function useCreateTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Parameters<typeof api.createTransaction>[0]) =>
      api.createTransaction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
    },
  })
}

export function useFlagTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.flagTransaction(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

export function useBatchUpdate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { transaction_ids: string[]; category: string; deductible_status: string; notes?: string }) =>
      api.batchUpdate(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
    },
  })
}

export function useBatchFlag() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { transaction_ids: string[]; reason: string }) =>
      api.batchFlag(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}
