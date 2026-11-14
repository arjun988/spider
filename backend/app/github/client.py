"""Authenticated GitHub API client for App installations."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger
from app.github.authentication import get_installation_token

logger = get_logger(__name__)

API = "https://api.github.com"


class GitHubClient:
    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self._token = get_installation_token(installation_id)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{API}{path}"
        with httpx.Client(timeout=60.0, headers=self.headers) as client:
            response = client.request(method, url, **kwargs)
            if response.status_code == 204:
                return None
            response.raise_for_status()
            if not response.content:
                return None
            return response.json()

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self._request("DELETE", path, **kwargs)

    def list_installation_repos(self) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get(
                "/installation/repositories",
                params={"per_page": 100, "page": page},
            )
            batch = data.get("repositories", [])
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def get_pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self.get(f"/repos/{owner}/{repo}/pulls/{number}")

    def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.get(
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    def get_pull_request_commits(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        commits: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.get(
                f"/repos/{owner}/{repo}/pulls/{number}/commits",
                params={"per_page": 100, "page": page},
            )
            commits.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return commits

    def compare_commits(self, owner: str, repo: str, base: str, head: str) -> dict[str, Any]:
        return self.get(f"/repos/{owner}/{repo}/compare/{base}...{head}")

    def get_file_contents(
        self, owner: str, repo: str, path: str, ref: str
    ) -> dict[str, Any]:
        return self.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )

    def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str,
        event: str,
        comments: list[dict[str, Any]] | None = None,
        commit_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"body": body, "event": event}
        if commit_id:
            payload["commit_id"] = commit_id
        if comments:
            payload["comments"] = comments
        return self.post(f"/repos/{owner}/{repo}/pulls/{number}/reviews", json=payload)

    def create_issue_comment(
        self, owner: str, repo: str, number: int, body: str
    ) -> dict[str, Any]:
        return self.post(
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body},
        )

    def get_clone_url(self, owner: str, repo: str) -> str:
        data = self.get(f"/repos/{owner}/{repo}")
        return data["clone_url"]

    def authenticated_clone_url(self, owner: str, repo: str) -> str:
        """Clone URL with installation token embedded (server-side only)."""
        return f"https://x-access-token:{self._token}@github.com/{owner}/{repo}.git"

    def create_check_run(
        self,
        owner: str,
        repo: str,
        *,
        name: str,
        head_sha: str,
        status: str = "queued",
        conclusion: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        details_url: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
        }
        if details_url:
            payload["details_url"] = details_url
        if status == "completed":
            payload["conclusion"] = conclusion or "neutral"
            payload["output"] = {
                "title": title or name,
                "summary": summary or "",
            }
        elif title or summary:
            payload["output"] = {
                "title": title or name,
                "summary": summary or "",
            }
        return self.post(f"/repos/{owner}/{repo}/check-runs", json=payload)

    def update_check_run(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
        *,
        status: str | None = None,
        conclusion: str | None = None,
        title: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if status:
            payload["status"] = status
        if status == "completed" or conclusion:
            payload["conclusion"] = conclusion or "neutral"
        if title or summary:
            payload["output"] = {
                "title": title or "Spider Review",
                "summary": summary or "",
            }
        return self.patch(f"/repos/{owner}/{repo}/check-runs/{check_run_id}", json=payload)