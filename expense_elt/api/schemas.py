from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# --- Auth models ---

class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., max_length=4096)


class AuthUserResponse(BaseModel):
    email: str
    name: str = ""
    picture: str = ""
    role: str = "owner"
    permission: str = "full"
    error: str | None = None


# --- Review models ---

class ReviewDecisionRequest(BaseModel):
    category: str = Field(..., max_length=200)
    deductible_status: Literal["full", "partial", "personal"]
    deductible_amount: float = Field(..., ge=0)
    notes: str = Field("", max_length=1000)


class BatchReviewRequest(BaseModel):
    merchant_normalized: str = Field(..., max_length=500)
    category: str = Field(..., max_length=200)
    deductible_status: Literal["full", "partial", "personal"]
    notes: str = Field("", max_length=1000)
    save_rule: bool = False
    rule_keyword: str = Field("", max_length=500)


class InstitutionBreakdown(BaseModel):
    institution: str
    raw_count: int
    normalized_count: int
    categorized_count: int
    review_count: int
    business_count: int


class PipelineStatusResponse(BaseModel):
    raw_count: int
    normalized_count: int
    categorized_count: int
    review_count: int
    reviewed_count: int
    business_count: int
    personal_count: int
    total_deductible: float
    pipeline_running: bool
    by_institution: list[InstitutionBreakdown]


class TransactionResponse(BaseModel):
    transaction_id: str
    raw_id: Optional[str] = None
    institution: Optional[str] = None
    source_file: Optional[str] = None
    page_number: Optional[int] = None
    transaction_date: Optional[str] = None
    posted_date: Optional[str] = None
    merchant_raw: Optional[str] = None
    merchant_normalized: Optional[str] = None
    description_raw: Optional[str] = None
    original_amount: Optional[float] = None
    currency: Optional[str] = None
    is_credit: Optional[bool] = None
    dedupe_hash: Optional[str] = None
    normalized_at: Optional[str] = None
    category: Optional[str] = None
    deductible_status: Optional[str] = None
    deductible_amount: Optional[float] = None
    confidence: Optional[float] = None
    review_required: Optional[bool] = None
    rule_applied: Optional[str] = None
    notes: Optional[str] = None


class TransactionsListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    total_amount: float


class ReviewQueueResponse(BaseModel):
    transactions: list[dict[str, Any]]
    total: int


class CategorySummaryItem(BaseModel):
    category: str
    transaction_count: int
    total_original: float
    total_deductible: float


class SummaryResponse(BaseModel):
    totals: dict[str, Any]
    by_category: list[CategorySummaryItem]


class LLMCategorizeRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = Field(None, max_length=256)
    dry_run: bool = False
    force: bool = False


class RunAllRequest(BaseModel):
    use_llm: bool = False
    provider: str | None = None
    model: str | None = None
    force: bool = False


class ResetRequest(BaseModel):
    level: Literal["soft", "medium", "hard"] = "soft"


class ResetResponse(BaseModel):
    level: str
    deleted_count: int
    backed_up: list[str]
    message: str


class PipelineResultResponse(BaseModel):
    step: str
    success: bool
    stats: dict[str, Any]
    message: str


# --- Accountant management models ---

class InviteAccountantRequest(BaseModel):
    email: str = Field(..., max_length=320)
    permission: Literal["view", "view_flag"] = "view"


class UpdateAccountantRequest(BaseModel):
    permission: Literal["view", "view_flag"]


class AccountantResponse(BaseModel):
    email: str
    role: str = "accountant"
    permission: str
    status: str
    invited_by: str
    invited_at: str | None = None
    last_login: str | None = None


class FlagTransactionRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class BatchUpdateRequest(BaseModel):
    transaction_ids: list[str] = Field(..., min_length=1, max_length=500)
    category: str = Field(..., max_length=200)
    deductible_status: Literal["full", "partial", "personal"]
    notes: str = Field("", max_length=1000)


class BatchFlagRequest(BaseModel):
    transaction_ids: list[str] = Field(..., min_length=1, max_length=500)
    reason: str = Field(..., min_length=1, max_length=1000)


class CreateTransactionRequest(BaseModel):
    merchant_name: str = Field(..., min_length=1, max_length=500)
    original_amount: float = Field(..., gt=0)
    transaction_date: str = Field(..., max_length=10)  # YYYY-MM-DD
    category: str = Field(..., max_length=200)
    deductible_status: Literal["full", "partial", "personal"]
    deductible_amount: float | None = Field(None, ge=0)
    institution: str = Field("Manual", max_length=200)
    notes: str = Field("", max_length=1000)
    is_credit: bool = False
