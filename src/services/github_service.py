"""GitHub service for repository creation and file operations."""

import base64
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubServiceError(Exception):
    """Base exception for GitHub service errors."""

    pass


class GitHubAuthenticationError(GitHubServiceError):
    """Exception raised for authentication failures."""

    pass


class GitHubResourceNotFoundError(GitHubServiceError):
    """Exception raised when a requested resource is not found."""

    pass


class GitHubConflictError(GitHubServiceError):
    """Exception raised when a conflict occurs (e.g., existing resource)."""

    pass


class GitHubRateLimitError(GitHubServiceError):
    """Exception raised when rate limit is exceeded."""

    pass


class GitHubService:
    """Service for interacting with GitHub API for repository and file operations."""

    BASE_URL = "https://api.github.com"
    API_VERSION = "2022-11-28"
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3

    def __init__(
        self,
        token: str,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        """Initialize GitHub service with authentication and configuration.

        Args:
            token: GitHub personal access token.
            base_url: Custom GitHub API base URL (for GitHub Enterprise).
            timeout: Request timeout in seconds.

        Raises:
            ValueError: If token is empty or invalid.
        """
        if not token or not token.strip():
            raise ValueError("GitHub token must be a non-empty string.")

        self._token = token.strip()
        self._base_url = (base_url or self.BASE_URL).rstrip("/")
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create and configure a requests session with retry logic.

        Returns:
            Configured requests Session object.
        """
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": self.API_VERSION,
                "User-Agent": "GitHubService/1.0",
            }
        )

        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "POST", "PATCH", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Process API response and handle errors.

        Args:
            response: Response object from requests library.

        Returns:
            Parsed JSON response as dictionary.

        Raises:
            GitHubAuthenticationError: If authentication fails.
            GitHubResourceNotFoundError: If resource is not found.
            GitHubConflictError: If conflict occurs.
            GitHubRateLimitError: If rate limit is exceeded.
            GitHubServiceError: For other API errors.
        """
        if response.status_code == 401:
            raise GitHubAuthenticationError(
                "Authentication failed. Check your GitHub token."
            )
        elif response.status_code == 403:
            if "rate limit" in response.text.lower():
                raise GitHubRateLimitError(
                    "GitHub API rate limit exceeded. Please try again later."
                )
            raise GitHubAuthenticationError(
                f"Access forbidden: {response.text}"
            )
        elif response.status_code == 404:
            raise GitHubResourceNotFoundError(
                f"Resource not found: {response.url}"
            )
        elif response.status_code == 409:
            raise GitHubConflictError(
                f"Conflict error: {response.text}"
            )
        elif response.status_code >= 500:
            raise GitHubServiceError(
                f"GitHub server error ({response.status_code}): {response.text}"
            )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise GitHubServiceError(
                f"HTTP error {response.status_code}: {response.text}"
            ) from exc

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise GitHubServiceError(
                f"Invalid JSON response: {response.text}"
            ) from exc

    def create_repository(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = False,
        auto_init: bool = False,
        gitignore_template: Optional[str] = None,
        license_template: Optional[str] = None,
        organization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new GitHub repository.

        Args:
            name: Repository name.
            description: Repository description.
            private: Whether repository should be private.
            auto_init: Whether to initialize with README.
            gitignore_template: Gitignore template name.
            license_template: License template name.
            organization: Organization name (None for personal account).

        Returns:
            Dictionary containing repository information.

        Raises:
            ValueError: If repository name is invalid.
            GitHubConflictError: If repository already exists.
            GitHubServiceError: For other API errors.
        """
        if not name or not name.strip():
            raise ValueError("Repository name must be a non-empty string.")

        if not name.strip().isidentifier() and not all(
            c.isalnum() or c in "._-" for c in name.strip()
        ):
            raise ValueError(
                "Repository name contains invalid characters. "
                "Use alphanumeric characters, hyphens, underscores, or periods."
            )

        payload: Dict[str, Any] = {
            "name": name.strip(),
            "description": description or "",
            "private": private,
            "auto_init": auto_init,
        }

        if gitignore_template:
            payload["gitignore_template"] = gitignore_template
        if license_template:
            payload["license_template"] = license_template

        if organization:
            url = f"{self._base_url}/orgs/{organization}/repos"
        else:
            url = f"{self._base_url}/user/repos"

        logger.info(
            "Creating repository '%s' in %s",
            name,
            f"organization '{organization}'" if organization else "personal account",
        )

        try:
            response = self._session.post(
                url, json=payload, timeout=self._timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to create repository: {exc}"
            ) from exc

    def get_repository(
        self, owner: str, repo: str
    ) -> Dict[str, Any]:
        """Get repository information.

        Args:
            owner: Repository owner (user or organization).
            repo: Repository name.

        Returns:
            Dictionary containing repository information.

        Raises:
            GitHubResourceNotFoundError: If repository is not found.
            GitHubServiceError: For other API errors.
        """
        if not owner or not repo:
            raise ValueError("Owner and repo must be non-empty strings.")

        url = f"{self._base_url}/repos/{owner}/{repo}"

        logger.info("Fetching repository '%s/%s'", owner, repo)

        try:
            response = self._session.get(url, timeout=self._timeout)
            return self._handle_response(response)
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to get repository: {exc}"
            ) from exc

    def delete_repository(self, owner: str, repo: str) -> bool:
        """Delete a GitHub repository.

        Args:
            owner: Repository owner (user or organization).
            repo: Repository name.

        Returns:
            True if deletion was successful.

        Raises:
            GitHubResourceNotFoundError: If repository is not found.
            GitHubServiceError: For other API errors.
        """
        if not owner or not repo:
            raise ValueError("Owner and repo must be non-empty strings.")

        url = f"{self._base_url}/repos/{owner}/{repo}"

        logger.info("Deleting repository '%s/%s'", owner, repo)

        try:
            response = self._session.delete(url, timeout=self._timeout)
            self._handle_response(response)
            return True
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to delete repository: {exc}"
            ) from exc

    def get_file_content(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """Get file content from a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: File path in repository.
            ref: Branch name or commit SHA (default: default branch).

        Returns:
            Tuple of (decoded content, file SHA, encoding).

        Raises:
            GitHubResourceNotFoundError: If file is not found.
            GitHubServiceError: For other API errors.
        """
        if not all([owner, repo, path]):
            raise ValueError("Owner, repo, and path must be non-empty strings.")

        url = f"{self._base_url}/repos/{owner}/{repo}/contents/{path.lstrip('/')}"
        params = {}
        if ref:
            params["ref"] = ref

        logger.info("Fetching file '%s' from '%s/%s'", path, owner, repo)

        try:
            response = self._session.get(
                url, params=params, timeout=self._timeout
            )
            data = self._handle_response(response)

            encoding = data.get("encoding", "")
            content = data.get("content", "")
            sha = data.get("sha", "")

            if encoding == "base64":
                decoded_content = base64.b64decode(content).decode("utf-8")
            else:
                decoded_content = content

            return decoded_content, sha, encoding
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to get file content: {exc}"
            ) from exc

    def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        commit_message: str,
        branch: Optional[str] = None,
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a file in a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: File path in repository.
            content: File content as string.
            commit_message: Commit message.
            branch: Branch name (default: default branch).
            sha: File SHA (required for updating existing files).

        Returns:
            Dictionary containing commit information.

        Raises:
            ValueError: If required parameters are invalid.
            GitHubResourceNotFoundError: If repository or branch not found.
            GitHubConflictError: If file update requires SHA.
            GitHubServiceError: For other API errors.
        """
        if not all([owner, repo, path, content, commit_message]):
            raise ValueError(
                "Owner, repo, path, content, and commit_message are required."
            )

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload: Dict[str, Any] = {
            "message": commit_message,
            "content": encoded_content,
        }

        if branch:
            payload["branch"] = branch
        if sha:
            payload["sha"] = sha

        url = f"{self._base_url}/repos/{owner}/{repo}/contents/{path.lstrip('/')}"

        logger.info(
            "Creating/updating file '%s' in '%s/%s'", path, owner, repo
        )

        try:
            response = self._session.put(
                url, json=payload, timeout=self._timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to create/update file: {exc}"
            ) from exc

    def push_files(
        self,
        owner: str,
        repo: str,
        files: List[Dict[str, str]],
        commit_message: str,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Push multiple files to a repository in a single commit.

        Args:
            owner: Repository owner.
            repo: Repository name.
            files: List of file dictionaries with 'path' and 'content' keys.
            commit_message: Commit message.
            branch: Branch name (default: default branch).

        Returns:
            Dictionary containing commit information.

        Raises:
            ValueError: If parameters are invalid.
            GitHubServiceError: For API errors.
        """
        if not all([owner, repo, files, commit_message]):
            raise ValueError(
                "Owner, repo, files, and commit_message are required."
            )

        if not files:
            raise ValueError("Files list cannot be empty.")

        for file_entry in files:
            if "path" not in file_entry or "content" not in file_entry:
                raise ValueError(
                    "Each file entry must contain 'path' and 'content' keys."
                )

        # Get the latest commit SHA for the branch
        try:
            ref = branch or await self._get_default_branch(owner, repo)
            latest_commit_sha = self._get_ref_sha(owner, repo, f"heads/{ref}")
            tree_sha = self._get_commit_tree_sha(
                owner, repo, latest_commit_sha
            )
        except GitHubResourceNotFoundError as exc:
            raise GitHubServiceError(
                f"Branch '{ref}' not found in repository '{owner}/{repo}'"
            ) from exc

        # Create blobs for each file
        blobs = []
        for file_entry in files:
            blob_sha = self._create_blob(
                owner, repo, file_entry["content"]
            )
            blobs.append(
                {
                    "path": file_entry["path"],
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )

        # Create a new tree
        new_tree_sha = self._create_tree(
            owner, repo, tree_sha, blobs
        )

        # Create a commit
        commit_sha = self._create_commit(
            owner, repo, commit_message, new_tree_sha, [latest_commit_sha]
        )

        # Update the branch reference
        self._update_ref(owner, repo, f"heads/{ref}", commit_sha)

        logger.info(
            "Successfully pushed %d files to '%s/%s' on branch '%s'",
            len(files),
            owner,
            repo,
            ref,
        )

        return {
            "commit_sha": commit_sha,
            "branch": ref,
            "files_count": len(files),
        }

    def _get_default_branch(self, owner: str, repo: str) -> str:
        """Get the default branch name of a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Default branch name.

        Raises:
            GitHubResourceNotFoundError: If repository is not found.
        """
        repo_info = self.get_repository(owner, repo)
        return repo_info.get("default_branch", "main")

    def _get_ref_sha(self, owner: str, repo: str, ref: str) -> str:
        """Get the SHA of a Git reference.

        Args:
            owner: Repository owner.
            repo: Repository name.
            ref: Git reference (e.g., 'heads/main').

        Returns:
            SHA of the reference.

        Raises:
            GitHubResourceNotFoundError: If reference is not found.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/git/ref/{ref}"

        try:
            response = self._session.get(url, timeout=self._timeout)
            data = self._handle_response(response)
            return data["object"]["sha"]
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to get ref SHA: {exc}"
            ) from exc

    def _get_commit_tree_sha(self, owner: str, repo: str, commit_sha: str) -> str:
        """Get the tree SHA from a commit.

        Args:
            owner: Repository owner.
            repo: Repository name.
            commit_sha: Commit SHA.

        Returns:
            Tree SHA.

        Raises:
            GitHubResourceNotFoundError: If commit is not found.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/git/commits/{commit_sha}"

        try:
            response = self._session.get(url, timeout=self._timeout)
            data = self._handle_response(response)
            return data["tree"]["sha"]
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to get commit tree SHA: {exc}"
            ) from exc

    def _create_blob(self, owner: str, repo: str, content: str) -> str:
        """Create a Git blob.

        Args:
            owner: Repository owner.
            repo: Repository name.
            content: File content.

        Returns:
            Blob SHA.

        Raises:
            GitHubServiceError: For API errors.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/git/blobs"
        payload = {
            "content": content,
            "encoding": "utf-8",
        }

        try:
            response = self._session.post(
                url, json=payload, timeout=self._timeout
            )
            data = self._handle_response(response)
            return data["sha"]
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to create blob: {exc}"
            ) from exc

    def _create_tree(
        self,
        owner: str,
        repo: str,
        base_tree_sha: str,
        tree_items: List[Dict[str, Any]],
    ) -> str:
        """Create a Git tree.

        Args:
            owner: Repository owner.
            repo: Repository name.
            base_tree_sha: Base tree SHA.
            tree_items: List of tree item dictionaries.

        Returns:
            New tree SHA.

        Raises:
            GitHubServiceError: For API errors.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/git/trees"
        payload = {
            "base_tree": base_tree_sha,
            "tree": tree_items,
        }

        try:
            response = self._session.post(
                url, json=payload, timeout=self._timeout
            )
            data = self._handle_response(response)
            return data["sha"]
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to create tree: {exc}"
            ) from exc

    def _create_commit(
        self,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parent_shas: List[str],
    ) -> str:
        """Create a Git commit.

        Args:
            owner: Repository owner.
            repo: Repository name.
            message: Commit message.
            tree_sha: Tree SHA.
            parent_shas: List of parent commit SHAs.

        Returns:
            Commit SHA.

        Raises:
            GitHubServiceError: For API errors.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/git/commits"
        payload = {
            "message": message,
            "tree": tree_sha,
            "parents": parent_shas,
        }

        try:
            response = self._session.post(
                url, json=payload, timeout=self._timeout
            )
            data = self._handle_response(response)
            return data["sha"]
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to create commit: {exc}"
            ) from exc

    def _update_ref(
        self, owner: str, repo: str, ref: str, sha: str
    ) -> Dict[str, Any]:
        """Update a Git reference.

        Args:
            owner: Repository owner.
            repo: Repository name.
            ref: Git reference (e.g., 'heads/main').
            sha: New SHA for the reference.

        Returns:
            Response data.

        Raises:
            GitHubServiceError: For API errors.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/git/refs/{ref}"
        payload = {
            "sha": sha,
            "force": False,
        }

        try:
            response = self._session.patch(
                url, json=payload, timeout=self._timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(
                f"Failed to update ref: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            self._session.close()

    def __enter__(self) -> "GitHubService":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Context manager exit."""
        self.close()