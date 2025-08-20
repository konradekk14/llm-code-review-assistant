from __future__ import annotations
from typing import Any, Dict, List, Optional

def _get_lb():
    from app.services.llm.load_balancer import get_load_balancer
    return get_load_balancer()

class ReviewService:
    def __init__(self, load_balancer=None):
        self.load_balancer = load_balancer or _get_lb()

    def create_review_prompt(self, pr_details: Dict[str, Any], changed_files: List[Dict[str, Any]]) -> str:
        from app.settings import settings  # local import to avoid import-time side effects

        files_summary = []
        total_changes = 0

        for file in changed_files:
            filename = file['filename']
            additions = file.get('additions', 0)
            deletions = file.get('deletions', 0)
            total_changes += additions + deletions

            patch = file.get('patch', '')

            if len(patch) < 2000:
                files_summary.append(f"\n**File: {filename}**\n```diff\n{patch}\n```")
            else:
                files_summary.append(f"\n**File: {filename}** (Large file - {additions}+ {deletions}- lines)")

        if total_changes > settings.max_changed_lines_reviewed:
            files_summary.append(
                f"\n**Warning**: Total changes ({total_changes}) exceed configured limit ({settings.max_changed_lines_reviewed})"
            )

        files_content = "\n".join(files_summary)

        prompt = f"""You are an expert software engineer performing a code review.

            Please analyze the following code changes and provide:
                1. **Security Issues**: Identify any potential security vulnerabilities
                2. **Bugs**: Spot logical errors or edge cases
                3. **Code Quality**: Suggest improvements for readability, performance, and maintainability
                4. **Best Practices**: Recommend following language/framework conventions
                5. **Testing**: Suggest areas that need test coverage

            Focus on the most critical issues first. Be specific and actionable in your feedback.

            Code Changes (Total: {total_changes} lines):
            {files_content}

            Provide your review in a clear, structured format:"""

        return prompt

    async def generate_review(self, pr_details: Dict[str, Any], changed_files: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        if not self.load_balancer:
            raise RuntimeError("Load balancer not configured")

        prompt = self.create_review_prompt(pr_details, changed_files)
        # lb handles health checks, selection, retries, and metadata
        result = await self.load_balancer.generate_review(prompt, **kwargs)
        return {
            "review": result.get("content") or result,
            "load_balancer": result.get("load_balancer"),
        }

    def lb_stats(self) -> Dict[str, Any]:
        return self.load_balancer.get_stats()
