import httpx
import re
from fastapi import HTTPException
from app.settings import settings

# this file is meant for interacting with the github api

class GitHubService:
    def __init__(self, token: str = None):
        self.token = token or settings.github_token
        self.headers = settings.get_github_headers() if self.token else {}
        self.base_url = settings.github_api_base

    def parse_pr_url(self, pr_url: str) -> tuple[str, str, int]:
        pattern = r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)$"
        match = re.match(pattern, pr_url)
        if not match:
            raise ValueError(
                "Invalid GitHub PR URL format. Expected: https://github.com/owner/repo/pull/number"
            )
        return match.group(1), match.group(2), int(match.group(3))

    async def _get(self, endpoint: str):
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, timeout=10.0)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

    async def _post(self, endpoint: str, payload: dict):
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
            if resp.status_code not in [200, 201]:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list:
        return await self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")

    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        return await self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")

    async def get_pr_details_and_files(self, owner: str, repo: str, pr_number: int):
        details = await self.get_pr_details(owner, repo, pr_number)
        files = await self.get_pr_files(owner, repo, pr_number)
        return details, files

    async def post_review_comment(self, owner: str, repo: str, pr_number: int, comment: str):
        return await self._post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments", {"body": comment}
        )

# global instance
github_service = GitHubService() if settings.is_github_configured() else None
