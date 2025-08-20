from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, Literal, List, Dict

# structure for the review request
class PRReviewRequest(BaseModel):
    pr_url: str
    auto_comment: bool = True
    llm_provider: Optional[str] = "auto"

# representation of a changed file
class FilePatch(BaseModel):
    path: str
    patch: str  # unified diff
    language: Optional[str] = None

# pr request information
class PRContext(BaseModel):
    owner: str
    repo: str
    pr_number: int
    title: str
    description: str
    branch: str
    base_branch: str
    author: str
    files: List[FilePatch]

Severity = Literal["info", "nit", "warn", "error", "security"]
Category = Literal["readability","style","bug","perf","security","test","docs"]

# represents a single code review (structure for detailed feedback essentially)
class ReviewFinding(BaseModel):
    file: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    severity: Severity
    category: Category
    title: str
    rationale: str
    suggestion: Optional[str] = None
    patch: Optional[str] = None
    references: List[str] = []

# finallyy, the model for the review result
class ReviewResult(BaseModel):
    summary: str
    findings: List[ReviewFinding]
    stats: Dict[str, int] = {}
    model: str
    latency_ms: int
