from fastapi import APIRouter, HTTPException, Depends
from app.models.review import PRReviewRequest
from app.services.github_service import github_service
from app.services.review.review_service import ReviewService
from app.services.llm.load_balancer import get_load_balancer

router = APIRouter()

# review service w/ the load balancer
def get_review_service() -> ReviewService:
    return ReviewService(load_balancer=get_load_balancer())

@router.post("/review-pr")
async def review_pull_request(
    request: PRReviewRequest,
    review_service: ReviewService = Depends(get_review_service)
):
    if not github_service:
        raise HTTPException(status_code=500, detail="GitHub not configured")

    # parse pr url and get pr details and changed files
    owner, repo, pr_number = github_service.parse_pr_url(request.pr_url)
    pr_details, changed_files = await github_service.get_pr_details_and_files(owner, repo, pr_number)

    if not changed_files:
        return {"message": "No files changed in this PR"}

    # review service -> load balancer -> provider
    review_result = await review_service.generate_review(pr_details, changed_files)

    if request.auto_comment:
        await github_service.post_review_comment(owner, repo, pr_number, review_result["review"])

    return {
        "status": "success",
        "files_reviewed": len(changed_files),
        "review_content": review_result["review"],
        "llm_provider_used": review_result["load_balancer"]["provider_used"],
        "provider_status": review_result["load_balancer"]["provider_status"],
        "latency_ms": review_result["load_balancer"]["latency_ms"]
    }
