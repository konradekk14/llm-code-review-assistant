from pydantic import BaseModel
from typing import Optional

class PRReviewRequest(BaseModel):
    pr_url: str
    auto_comment: bool = True
    llm_provider: Optional[str] = "auto"
