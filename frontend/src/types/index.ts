export interface AuthUser {
  email: string
  name: string
  picture: string
  role: 'owner' | 'accountant'
  permission: 'full' | 'view' | 'view_flag'
}

export interface Transaction {
  transaction_id: string
  institution: string
  source_file: string
  transaction_date: string
  merchant_raw: string
  merchant_normalized: string
  description_raw: string
  original_amount: number
  is_credit: boolean
  category: string
  deductible_status: 'full' | 'partial' | 'personal' | 'needs_review'
  deductible_amount: number
  confidence: number
  review_required: boolean
  rule_applied: string
  notes: string
}

export interface ReviewTransaction extends Transaction {
  // extra fields from review queue join
}

export interface ReviewDecision {
  category: string
  deductible_status: 'full' | 'partial' | 'personal'
  deductible_amount: number
  notes: string
}

export interface BatchReviewDecision {
  merchant_normalized: string
  category: string
  deductible_status: 'full' | 'partial' | 'personal'
  notes: string
  save_rule?: boolean
  rule_keyword?: string
}

export interface KeywordRule {
  index: number
  keywords: string[]
  category: string
  confidence: number
}

export interface DeductionRule {
  index: number
  name: string
  merchant_pattern: string
  deductible_status: 'full' | 'partial' | 'personal'
  method: 'full' | 'percentage' | 'fixed_monthly' | 'personal'
  amount?: number
  percentage?: number
  category?: string
  start_date?: string
  end_date?: string
  notes?: string
}

export interface PipelineStatus {
  raw_count: number
  normalized_count: number
  categorized_count: number
  review_count: number
  reviewed_count: number
  business_count: number
  personal_count: number
  total_deductible: number
  pipeline_running: boolean
  by_institution: InstitutionBreakdown[]
}

export interface InstitutionBreakdown {
  institution: string
  raw_count: number
  normalized_count: number
  categorized_count: number
  review_count: number
  business_count: number
}

export interface CategorySummary {
  category: string
  transaction_count: number
  total_original: number
  total_deductible: number
}

export interface ConfigChangeEntry {
  timestamp: string
  config_file: string
  action: string
  detail: string
  source: string
}

export interface PipelineResult {
  step: string
  success: boolean
  stats: Record<string, any>
  message: string
}

export interface LLMConfig {
  provider: string
  model: string
  batch_size: number
  max_cost_per_run: number
  temperature: number
  suggested_models: Record<string, string[]>
  has_anthropic_key: boolean
  has_openai_key: boolean
}

export interface LLMProgressPoll {
  active: boolean
  type?: string
  batch_number?: number
  total_batches?: number
  cumulative_categorized?: number
  cumulative_cost_usd?: number
  cumulative_input_tokens?: number
  cumulative_output_tokens?: number
  memory_matched?: number
  llm_candidates?: number
  model?: string
}

export interface ResetResult {
  level: string
  deleted_count: number
  backed_up: string[]
  message: string
}

export interface LLMProgressEvent {
  type: 'start' | 'progress' | 'complete' | 'error' | 'heartbeat'
  // start
  memory_matched?: number
  llm_candidates?: number
  total_batches?: number
  model?: string
  // progress
  batch_number?: number
  cumulative_categorized?: number
  cumulative_cost_usd?: number
  cumulative_input_tokens?: number
  cumulative_output_tokens?: number
  // complete
  step?: string
  success?: boolean
  stats?: Record<string, any>
  message?: string
}

export interface AccountantUser {
  email: string
  role: string
  permission: string
  status: string
  invited_by: string
  invited_at: string | null
  last_login: string | null
}
