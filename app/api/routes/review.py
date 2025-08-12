from fastapi import APIRouter, HTTPException
from app.models.review import PRReviewRequest
from app.services.github_service import github_service
from app.services.review.review_service import ReviewService
from app.services.llm.openai_service import OpenAIService

router = APIRouter()
review_service = ReviewService()
llm_service = OpenAIService()

@router.post("/review-pr")
async def review_pull_request(request: PRReviewRequest):
    if not github_service:
        raise HTTPException(status_code=500, detail="GitHub not configured")

    owner, repo, pr_number = await github_service.parse_pr_url(request.pr_url)
    pr_details, changed_files = await github_service.get_pr_details_and_files(owner, repo, pr_number)

    if not changed_files:
        return {"message": "No files changed in this PR"}

    prompt = review_service.create_review_prompt(pr_details, changed_files)
    review_result = await llm_service.generate_review(prompt, request.llm_provider)

    if request.auto_comment:
        await github_service.post_review_comment(owner, repo, pr_number, review_result['content'])

    return {
        "status": "success",
        "files_reviewed": len(changed_files),
        "review_content": review_result['content'],
        "llm_provider_used": review_result['provider_used']
    }
