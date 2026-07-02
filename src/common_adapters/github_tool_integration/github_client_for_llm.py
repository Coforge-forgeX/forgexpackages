"""
GitHub Client for LLM Integration

A wrapper class for the PyGithub client that provides methods to fetch repository structure,
code, and inspect GitHub tokens for metadata. This class is designed for LLM integration.
"""

from github import Github
from typing import Any, Dict, List, Optional
import logging
import os
import asyncio
from pathlib import Path

from ..http_client import HTTPClient


# Decorator for tool registration
def agent_tool(func):
    """
    Decorator to mark a method as an agent tool.
    Only methods marked with this decorator will be available to the agent.
    
    Usage:
        @agent_tool
        def my_tool(self):
            pass
    """
    func._is_agent_tool = True
    return func


handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s @ %(name)s @ %(levelname)s @ %(message)s"
))

logger = logging.getLogger("github_client")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

env = os.getenv("ENV") or "dev"


class GitHubLLMWrapper:
    """
    A wrapper class for the PyGithub client that provides methods to fetch repository structure,
    code, and inspect GitHub tokens for metadata. This class is designed for LLM integration.
    """
    
    def __init__(self, token: str, github_repo_full_name: Optional[str] = None, branch_name: Optional[str] = None):
        """
        Initialize the GitHub client with connection parameters.
        Args:
            token: GitHub Personal Access Token (PAT)
            github_repo_full_name: Full repo name (e.g., 'username/repo') or None for token-only mode
            branch_name: Branch name to use (default: None for default branch)
        """
        logger.info(f"Initializing GitHubLLMWrapper for {'token-only mode' if github_repo_full_name is None else github_repo_full_name}")
        self._client = Github(token)
        self._http_client = HTTPClient(
            base_url="https://api.github.com",
            default_headers={
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github+json',
                'User-Agent': f'forgex-{env}-github-client/1.0'
            }
        )
        self._repo = self._client.get_repo(github_repo_full_name) if github_repo_full_name else None
        self._branch_name = branch_name

    @agent_tool
    def list_files(self, path: str = "") -> List[str]:
        """
        Recursively list all files in the repository.
        Args:
            path: Directory path to start from (default: root)
        Returns:
            List of file paths
        """
        files = []
        ref = self._branch_name
        contents = self._repo.get_contents(path, ref=ref) if ref else self._repo.get_contents(path)
        for content in contents:
            if content.type == "dir":
                files += self.list_files(content.path)
            else:
                files.append(content.path)
        return files

    @agent_tool
    def get_file_content(self, file_path: str) -> str:
        """
        Fetch the content of a file from the repository.
        Args:
            file_path: Path to the file in the repo
        Returns:
            File content as string
        """
        ref = self._branch_name
        file_content = self._repo.get_contents(file_path, ref=ref) if ref else self._repo.get_contents(file_path)
        return file_content.decoded_content.decode()

    @agent_tool
    def get_repo_structure_and_code(self) -> Dict[str, str]:
        """
        Return a dict mapping file paths to their contents.
        Returns:
            Dict[file_path, file_content]
        """
        logger.info(f"Fetching repo structure for branch: {self._branch_name or 'default'}")
        files = self.list_files()
        structure = {}
        for file_path in files:
            try:
                structure[file_path] = self.get_file_content(file_path)
            except Exception as e:
                structure[file_path] = f"Error reading file: {e}"
        return structure

    def analyze_and_suggest_changes(self, user_query: str) -> Dict[str, Any]:
        """
        Analyze the repo and suggest changes based on the user query.
        Args:
            user_query: The user's request or question
        Returns:
            Dict with structure and suggestions
        """
        structure = self.get_repo_structure_and_code()
        return {
            "structure": structure,
            "suggestions": [
                f"Analyze the codebase for: {user_query}",
                "Implement logic to suggest changes here."
            ]
        }

    def myself(self) -> dict:
        """
        Get information about the currently authenticated user.
        Returns:
            User info dict
        """
        logger.info("Fetching current GitHub user information")
        user = self._client.get_user()
        return {"login": user.login, "id": user.id, "name": user.name, "email": user.email}

    async def _fetch_token_headers(self) -> Dict[str, Any]:
        """Fetch token headers using the HTTP client."""
        response = await self._http_client.get("/user")
        return response

    async def get_token_scopes(self) -> Dict[str, Any]:
        """Return the GitHub token scope headers from the API response."""
        response = await self._fetch_token_headers()
        if response['status_code'] == 200:
            headers = response.get('headers', {})
            return {
                "scopes": headers.get("x-oauth-scopes", ""),
                "accepted_scopes": headers.get("x-accepted-oauth-scopes", ""),
                "rate_limit_remaining": headers.get("x-ratelimit-remaining"),
                "rate_limit_limit": headers.get("x-ratelimit-limit"),
                "rate_limit_reset": headers.get("x-ratelimit-reset")
            }
        else:
            return {"error": response.get('error', 'Unknown error')}

    def get_rate_limit(self) -> Dict[str, Any]:
        """Return the current GitHub API rate limit for the token."""
        try:
            rate_limit = self._client.get_rate_limit()
            core = rate_limit.core
            search = rate_limit.search
            return {
                "core": {
                    "limit": getattr(core, "limit", None),
                    "remaining": getattr(core, "remaining", None),
                    "reset": getattr(core, "reset", None)
                },
                "search": {
                    "limit": getattr(search, "limit", None),
                    "remaining": getattr(search, "remaining", None),
                    "reset": getattr(search, "reset", None)
                }
            }
        except Exception as e:
            logger.warning(f"Unable to read rate limit: {e}")
            return {"error": str(e)}

    @agent_tool
    def get_repo_languages(self, repo_full_name: str) -> Dict[str, Any]:
        """Return programming languages used in the repository with their byte sizes."""
        try:
            repo = self._client.get_repo(repo_full_name)
            languages = repo.get_languages()
            return dict(languages)
        except Exception as e:
            logger.warning(f"Unable to fetch languages for {repo_full_name}: {e}")
            return {"error": str(e)}

    async def get_accessible_repos_paginated(self, page: int = 1, per_page: int = 30, sort: str = "updated") -> Dict[str, Any]:
        """Return paginated list of accessible repositories."""
        try:
            params = {
                "page": page,
                "per_page": min(per_page, 100),
                "sort": sort,
                "type": "all"
            }
            response = await self._http_client.get("/user/repos", params=params)
            if response['status_code'] == 200:
                repos = []
                for repo in response['data']:
                    repos.append({
                        "full_name": repo.get("full_name"),
                        "private": repo.get("private"),
                        "html_url": repo.get("html_url"),
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "updated_at": repo.get("updated_at"),
                        "permissions": repo.get("permissions", {})
                    })
                return {
                    "repos": repos,
                    "page": page,
                    "per_page": per_page,
                    "total_count": len(repos)
                }
            else:
                return {"error": response.get('error', 'Unknown error'), "repos": []}
        except Exception as e:
            logger.warning(f"Unable to fetch paginated repos: {e}")
            return {"error": str(e), "repos": []}

    async def get_repo_branches_paginated(self, repo_full_name: str, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
        """Return paginated list of branches for a repository."""
        try:
            params = {
                "page": page,
                "per_page": min(per_page, 100)
            }
            response = await self._http_client.get(f"/repos/{repo_full_name}/branches", params=params)
            if response['status_code'] == 200:
                branches = []
                for branch in response['data']:
                    branches.append({
                        "name": branch.get("name"),
                        "protected": branch.get("protected", False),
                        "commit_sha": branch.get("commit", {}).get("sha")
                    })
                return {
                    "branches": branches,
                    "page": page,
                    "per_page": per_page,
                    "repo_full_name": repo_full_name
                }
            else:
                return {"error": response.get('error', 'Unknown error'), "branches": []}
        except Exception as e:
            logger.warning(f"Unable to fetch branches for {repo_full_name}: {e}")
            return {"error": str(e), "branches": []}

    async def validate_token(self) -> Dict[str, Any]:
        """Validate if the GitHub token is valid."""
        try:
            response = await self._http_client.get("/user")
            if response['status_code'] == 200:
                user_data = response['data']
                return {
                    "valid": True,
                    "user": {
                        "login": user_data.get("login"),
                        "id": user_data.get("id"),
                        "name": user_data.get("name"),
                        "type": user_data.get("type")
                    }
                }
            elif response['status_code'] == 401:
                return {"valid": False, "error": "Invalid token"}
            else:
                return {"valid": False, "error": response.get('error', 'Unknown error')}
        except Exception as e:
            logger.warning(f"Unable to validate token: {e}")
            return {"valid": False, "error": str(e)}

    @agent_tool
    async def get_open_pull_requests(self, repo_full_name: str, page: int = 1, per_page: int = 30,
                                     state: str = "open", base_branch: Optional[str] = None) -> Dict[str, Any]:
        """Return paginated list of pull requests for a repository.
        
        Args:
            repo_full_name: Repository name in format 'owner/repo'
            page: Page number for pagination (default: 1)
            per_page: Number of PRs per page, max 100 (default: 30)
            state: PR state filter - 'open', 'closed', or 'all' (default: 'open')
            base_branch: Optional filter by destination/base branch name (e.g., 'main', 'develop')
        
        Returns:
            dict: Paginated list of pull requests with branch information
        """
        try:
            params = {
                "page": page,
                "per_page": min(per_page, 100),
                "state": state
            }
            if base_branch:
                params["base"] = base_branch
            
            response = await self._http_client.get(f"/repos/{repo_full_name}/pulls", params=params)
            if response['status_code'] == 200:
                prs = []
                for pr in response['data']:
                    merged_at = pr.get("merged_at")
                    closed_at = pr.get("closed_at")
                    is_merged = merged_at is not None
                    
                    prs.append({
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "state": pr.get("state"),
                        "source": pr.get("head", {}).get("ref"),
                        "destination": pr.get("base", {}).get("ref"),
                        "created_at": pr.get("created_at"),
                        "updated_at": pr.get("updated_at"),
                        "user": {
                            "login": pr.get("user", {}).get("login"),
                            "id": pr.get("user", {}).get("id")
                        },
                        "html_url": pr.get("html_url"),
                        "draft": pr.get("draft", False),
                        "merged": is_merged,
                        "merged_at": merged_at,
                        "closed_at": closed_at,
                    })
                return {
                    "pull_requests": prs,
                    "page": page,
                    "per_page": per_page,
                    "repo_full_name": repo_full_name,
                    "state": state,
                    "base_branch": base_branch
                }
            else:
                return {"error": response.get('error', 'Unknown error'), "pull_requests": []}
        except Exception as e:
            logger.warning(f"Unable to fetch PRs for {repo_full_name}: {e}")
            return {"error": str(e), "pull_requests": []}

    @agent_tool
    async def get_pull_request_commits(self, repo_full_name: str, pr_number: int, page: int = 1,
                                       per_page: int = 30) -> Dict[str, Any]:
        """Return paginated list of commits for a pull request.
        
        Args:
            repo_full_name: Repository name in format 'owner/repo'
            pr_number: Pull request number
            page: Page number for pagination (default: 1)
            per_page: Number of commits per page, max 100 (default: 30)
        
        Returns:
            dict: Paginated list of commits that are part of the PR (from its source branch).
        """
        try:
            params = {
                "page": page,
                "per_page": min(per_page, 100)
            }
            response = await self._http_client.get(f"/repos/{repo_full_name}/pulls/{pr_number}/commits", params=params)
            if response['status_code'] == 200:
                commits = []
                for commit in response['data']:
                    commits.append({
                        "sha": commit.get("sha"),
                        "message": commit.get("commit", {}).get("message"),
                        "author": {
                            "name": commit.get("commit", {}).get("author", {}).get("name"),
                            "email": commit.get("commit", {}).get("author", {}).get("email"),
                            "date": commit.get("commit", {}).get("author", {}).get("date")
                        },
                        "committer": {
                            "name": commit.get("commit", {}).get("committer", {}).get("name"),
                            "email": commit.get("commit", {}).get("committer", {}).get("email"),
                            "date": commit.get("commit", {}).get("committer", {}).get("date")
                        },
                        "html_url": commit.get("html_url")
                    })
                return {
                    "commits": commits,
                    "page": page,
                    "per_page": per_page,
                    "repo_full_name": repo_full_name,
                    "pr_number": pr_number
                }
            else:
                return {"error": response.get('error', 'Unknown error'), "commits": []}
        except Exception as e:
            logger.warning(f"Unable to fetch commits for PR {pr_number} in {repo_full_name}: {e}")
            return {"error": str(e), "commits": []}

    @agent_tool
    async def get_repo_commits(self, repo_full_name: str, branch: Optional[str] = None, page: int = 1,
                               per_page: int = 30) -> Dict[str, Any]:
        """Get a paginated list of commits for a GitHub repository.
        
        Args:
            repo_full_name: Repository name in format 'owner/repo'
            branch: Optional branch name to filter commits (e.g., 'main', 'develop'). 
                   If not specified, uses the repository's default branch
            page: Page number for pagination (default: 1)
            per_page: Number of commits per page, max 100 (default: 30)
        
        Returns:
            dict: Paginated list of commits for the specified branch, with most recent commits first
        """
        try:
            params = {
                "page": page,
                "per_page": min(per_page, 100)
            }
            if branch:
                params["sha"] = branch

            response = await self._http_client.get(f"/repos/{repo_full_name}/commits", params=params)
            if response['status_code'] == 200:
                commits = []
                for commit in response['data']:
                    commits.append({
                        "sha": commit.get("sha"),
                        "message": commit.get("commit", {}).get("message"),
                        "author": {
                            "name": commit.get("commit", {}).get("author", {}).get("name"),
                            "email": commit.get("commit", {}).get("author", {}).get("email"),
                            "date": commit.get("commit", {}).get("author", {}).get("date")
                        },
                        "committer": {
                            "name": commit.get("commit", {}).get("committer", {}).get("name"),
                            "email": commit.get("commit", {}).get("committer", {}).get("email"),
                            "date": commit.get("commit", {}).get("committer", {}).get("date")
                        },
                        "html_url": commit.get("html_url")
                    })
                return {
                    "commits": commits,
                    "page": page,
                    "per_page": per_page,
                    "repo_full_name": repo_full_name,
                    "branch": branch
                }
            else:
                return {"error": response.get('error', 'Unknown error'), "commits": []}
        except Exception as e:
            logger.warning(f"Unable to fetch commits for {repo_full_name}: {e}")
            return {"error": str(e), "commits": []}

    def _clean_error_entries(self, obj: Any) -> Any:
        """Clean error entries from nested dictionaries."""
        if isinstance(obj, dict):
            cleaned = {}
            for key, value in obj.items():
                if isinstance(value, dict) and "error" in value:
                    continue
                nested = self._clean_error_entries(value)
                if nested is None:
                    continue
                cleaned[key] = nested
            return cleaned
        if isinstance(obj, list):
            cleaned_list = [self._clean_error_entries(item) for item in obj if item is not None]
            return [item for item in cleaned_list if item != {} and item != []]
        return obj

    async def token_info(self) -> Dict[str, Any]:
        """Return all available metadata that can be gleaned from the GitHub token."""
        authenticated_user = self._client.get_user()
        user_info = {
            "login": authenticated_user.login,
            "id": authenticated_user.id,
            "name": authenticated_user.name,
            "email": authenticated_user.email,
            "type": authenticated_user.type,
            "site_admin": authenticated_user.site_admin
        }

        orgs = []
        try:
            orgs = [
                {
                    "login": org.login,
                    "id": org.id,
                    "name": org.name,
                    "url": org.url
                }
                for org in authenticated_user.get_orgs()
            ]
        except Exception as e:
            logger.warning(f"Unable to fetch organizations: {e}")
            orgs = []

        emails = []
        try:
            emails = [email.email for email in authenticated_user.get_emails()]
        except Exception as e:
            logger.warning(f"Unable to fetch emails: {e}")
            emails = []

        token_scopes = await self.get_token_scopes()
        info = {
            "authenticated_user": user_info,
            "token_scopes": token_scopes,
            "rate_limit": self.get_rate_limit(),
            "organizations": orgs,
            "emails": emails
        }

        return self._clean_error_entries(info)

    def __getattr__(self, name: str):
        """
        Dynamically proxy any method calls not explicitly defined to the underlying PyGithub repo client.
        Args:
            name: The method name being accessed
        """
        logger.debug(f"Proxying method call to underlying GitHub client: {name}")
        return getattr(self._repo, name)
