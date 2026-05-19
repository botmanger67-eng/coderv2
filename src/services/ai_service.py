"""AI service for code generation using language models."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import aiohttp
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config.settings import Settings
from src.exceptions import (
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIAuthenticationError,
    AIResponseError,
)
from src.schemas.ai import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelConfig,
    PromptTemplate,
    GenerationMetrics,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AIModelProvider(Enum):
    """Supported AI model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    LOCAL = "local"


@dataclass
class AIServiceConfig:
    """Configuration for AI service."""
    provider: AIModelProvider = AIModelProvider.OPENAI
    api_key: str = ""
    api_base_url: str = ""
    model_name: str = "gpt-4"
    max_retries: int = 3
    timeout_seconds: int = 30
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: List[str] = field(default_factory=list)
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 90000


class AIService:
    """Service for interacting with AI models for code generation."""

    def __init__(self, config: Optional[AIServiceConfig] = None):
        """Initialize AI service with configuration.

        Args:
            config: Service configuration. If None, loads from settings.

        Raises:
            AIServiceError: If initialization fails.
        """
        self.config = config or self._load_config()
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = RateLimiter(
            rpm=self.config.rate_limit_rpm,
            tpm=self.config.rate_limit_tpm
        )
        self._metrics = GenerationMetrics()

    def _load_config(self) -> AIServiceConfig:
        """Load configuration from application settings.

        Returns:
            AIServiceConfig instance.

        Raises:
            AIServiceError: If configuration loading fails.
        """
        try:
            settings = Settings()
            return AIServiceConfig(
                provider=AIModelProvider(settings.AI_PROVIDER),
                api_key=settings.AI_API_KEY,
                api_base_url=settings.AI_API_BASE_URL,
                model_name=settings.AI_MODEL_NAME,
                max_retries=settings.AI_MAX_RETRIES,
                timeout_seconds=settings.AI_TIMEOUT_SECONDS,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                top_p=settings.AI_TOP_P,
                frequency_penalty=settings.AI_FREQUENCY_PENALTY,
                presence_penalty=settings.AI_PRESENCE_PENALTY,
                stop_sequences=settings.AI_STOP_SEQUENCES,
                rate_limit_rpm=settings.AI_RATE_LIMIT_RPM,
                rate_limit_tpm=settings.AI_RATE_LIMIT_TPM,
            )
        except Exception as e:
            logger.error(f"Failed to load AI configuration: {e}")
            raise AIServiceError(f"Configuration loading failed: {e}") from e

    async def __aenter__(self) -> "AIService":
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session exists."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (AITimeoutError, AIRateLimitError, aiohttp.ClientError)
        ),
        reraise=True,
    )
    async def generate_code(
        self,
        request: CodeGenerationRequest,
    ) -> CodeGenerationResponse:
        """Generate code using AI model.

        Args:
            request: Code generation request parameters.

        Returns:
            CodeGenerationResponse with generated code and metadata.

        Raises:
            AIServiceError: If generation fails.
            AITimeoutError: If request times out.
            AIRateLimitError: If rate limit exceeded.
            AIAuthenticationError: If authentication fails.
            AIResponseError: If response parsing fails.
        """
        await self._ensure_session()
        await self._rate_limiter.acquire()

        start_time = asyncio.get_event_loop().time()

        try:
            prompt = self._build_prompt(request)
            headers = self._build_headers()
            payload = self._build_payload(prompt, request.model_config)

            async with self._session.post(
                self._get_api_url(),
                headers=headers,
                json=payload,
            ) as response:
                await self._handle_response_errors(response)
                response_data = await response.json()

            generated_code = self._parse_response(response_data)
            self._update_metrics(start_time, generated_code, request)

            return CodeGenerationResponse(
                code=generated_code,
                model=self.config.model_name,
                provider=self.config.provider.value,
                tokens_used=self._extract_token_usage(response_data),
                generation_time=asyncio.get_event_loop().time() - start_time,
                success=True,
            )

        except asyncio.TimeoutError as e:
            logger.error(f"AI request timed out: {e}")
            raise AITimeoutError(f"Request timed out after {self.config.timeout_seconds}s") from e
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                raise AIRateLimitError("Rate limit exceeded") from e
            elif e.status == 401:
                raise AIAuthenticationError("Authentication failed") from e
            raise AIServiceError(f"HTTP error {e.status}: {e.message}") from e
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise AIResponseError(f"Invalid response format: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in AI service: {e}")
            raise AIServiceError(f"Code generation failed: {e}") from e

    def _build_prompt(self, request: CodeGenerationRequest) -> str:
        """Build prompt from request parameters.

        Args:
            request: Code generation request.

        Returns:
            Formatted prompt string.
        """
        template = PromptTemplate(
            system="You are an expert software engineer. Generate high-quality, production-ready code.",
            user="""Generate {language} code for the following task:

Task: {task_description}

Requirements:
{requirements}

Constraints:
{constraints}

Context:
{context}

Please provide:
1. Complete implementation
2. Type hints
3. Error handling
4. Docstrings
5. Unit tests""",
        )

        return template.user.format(
            language=request.language,
            task_description=request.task_description,
            requirements=self._format_list(request.requirements),
            constraints=self._format_list(request.constraints),
            context=request.context or "No additional context provided.",
        )

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for API request.

        Returns:
            Dictionary of headers.

        Raises:
            AIAuthenticationError: If API key is missing.
        """
        if not self.config.api_key:
            raise AIAuthenticationError("API key not configured")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        if self.config.provider == AIModelProvider.AZURE:
            headers["api-key"] = self.config.api_key

        return headers

    def _build_payload(
        self,
        prompt: str,
        model_config: Optional[ModelConfig],
    ) -> Dict[str, Any]:
        """Build request payload for AI API.

        Args:
            prompt: Formatted prompt string.
            model_config: Optional model configuration overrides.

        Returns:
            Dictionary payload for API request.
        """
        config = model_config or ModelConfig()

        payload = {
            "model": config.model_name or self.config.model_name,
            "messages": [
                {"role": "system", "content": "You are an expert software engineer."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": config.max_tokens or self.config.max_tokens,
            "temperature": config.temperature or self.config.temperature,
            "top_p": config.top_p or self.config.top_p,
            "frequency_penalty": config.frequency_penalty or self.config.frequency_penalty,
            "presence_penalty": config.presence_penalty or self.config.presence_penalty,
            "stop": config.stop_sequences or self.config.stop_sequences or None,
        }

        if self.config.provider == AIModelProvider.ANTHROPIC:
            payload = self._convert_to_anthropic_format(payload)

        return payload

    def _convert_to_anthropic_format(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI format payload to Anthropic format.

        Args:
            payload: OpenAI format payload.

        Returns:
            Anthropic format payload.
        """
        messages = payload.pop("messages", [])
        system_message = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)

        return {
            "model": payload.pop("model"),
            "system": system_message,
            "messages": user_messages,
            "max_tokens": payload.pop("max_tokens"),
            "temperature": payload.pop("temperature"),
            "top_p": payload.pop("top_p"),
            "stop_sequences": payload.pop("stop", None),
        }

    def _get_api_url(self) -> str:
        """Get API URL based on provider.

        Returns:
            API endpoint URL.

        Raises:
            AIServiceError: If URL configuration is invalid.
        """
        if self.config.api_base_url:
            return self.config.api_base_url

        urls = {
            AIModelProvider.OPENAI: "https://api.openai.com/v1/chat/completions",
            AIModelProvider.ANTHROPIC: "https://api.anthropic.com/v1/messages",
            AIModelProvider.AZURE: "https://{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions?api-version=2023-05-15",
        }

        url = urls.get(self.config.provider)
        if not url:
            raise AIServiceError(f"Unsupported provider: {self.config.provider}")

        return url

    async def _handle_response_errors(self, response: aiohttp.ClientResponse) -> None:
        """Handle HTTP response errors.

        Args:
            response: HTTP response object.

        Raises:
            AIAuthenticationError: If 401 status.
            AIRateLimitError: If 429 status.
            AIServiceError: For other error statuses.
        """
        if response.status == 401:
            raise AIAuthenticationError("Invalid API key or authentication failed")
        elif response.status == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise AIRateLimitError(f"Rate limit exceeded. Retry after {retry_after}s")
        elif response.status >= 400:
            error_body = await response.text()
            raise AIServiceError(
                f"API error {response.status}: {error_body}"
            )

    def _parse_response(self, response_data: Dict[str, Any]) -> str:
        """Parse AI response to extract generated code.

        Args:
            response_data: Raw API response data.

        Returns:
            Extracted code string.

        Raises:
            AIResponseError: If response format is invalid.
        """
        try:
            if self.config.provider == AIModelProvider.ANTHROPIC:
                return self._parse_anthropic_response(response_data)
            else:
                return self._parse_openai_response(response_data)
        except (KeyError, IndexError, TypeError) as e:
            raise AIResponseError(f"Failed to parse response: {e}") from e

    def _parse_openai_response(self, response_data: Dict[str, Any]) -> str:
        """Parse OpenAI format response.

        Args:
            response_data: OpenAI API response.

        Returns:
            Generated code string.
        """
        choices = response_data["choices"]
        if not choices:
            raise AIResponseError("No choices in response")

        content = choices[0]["message"]["content"]
        return self._extract_code_from_content(content)

    def _parse_anthropic_response(self, response_data: Dict[str, Any]) -> str:
        """Parse Anthropic format response.

        Args:
            response_data: Anthropic API response.

        Returns:
            Generated code string.
        """
        content = response_data["content"]
        if not content:
            raise AIResponseError("No content in response")

        text_content = content[0]["text"]
        return self._extract_code_from_content(text_content)

    def _extract_code_from_content(self, content: str) -> str:
        """Extract code blocks from response content.

        Args:
            content: Raw response content.

        Returns:
            Extracted code string.
        """
        import re

        # Try to extract code blocks
        code_pattern = r"```(?:\w+)?\n(.*?)```"
        matches = re.findall(code_pattern, content, re.DOTALL)

        if matches:
            return "\n\n".join(match.strip() for match in matches)

        # If no code blocks found, return the content as-is
        return content.strip()

    def _extract_token_usage(self, response_data: Dict[str, Any]) -> Dict[str, int]:
        """Extract token usage from response.

        Args:
            response_data: API response data.

        Returns:
            Dictionary with token usage information.
        """
        usage = response_data.get("usage", {})
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    def _update_metrics(
        self,
        start_time: float,
        generated_code: str,
        request: CodeGenerationRequest,
    ) -> None:
        """Update generation metrics.

        Args:
            start_time: Generation start time.
            generated_code: Generated code string.
            request: Original request.
        """
        elapsed = asyncio.get_event_loop().time() - start_time
        self._metrics.total_requests += 1
        self._metrics.total_tokens += len(generated_code.split())
        self._metrics.average_response_time = (
            (self._metrics.average_response_time * (self._metrics.total_requests - 1) + elapsed)
            / self._metrics.total_requests
        )
        self._metrics.last_request_time = elapsed

        logger.info(
            f"Code generation completed: "
            f"language={request.language}, "
            f"time={elapsed:.2f}s, "
            f"code_length={len(generated_code)}"
        )

    def _format_list(self, items: List[str]) -> str:
        """Format list items for prompt.

        Args:
            items: List of strings.

        Returns:
            Formatted string.
        """
        if not items:
            return "None"
        return "\n".join(f"- {item}" for item in items)

    def get_metrics(self) -> GenerationMetrics:
        """Get current generation metrics.

        Returns:
            GenerationMetrics instance.
        """
        return self._metrics

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on AI service.

        Returns:
            Dictionary with health status information.
        """
        try:
            await self._ensure_session()
            headers = self._build_headers()

            async with self._session.get(
                self._get_api_url().replace("/chat/completions", "/models"),
                headers=headers,
            ) as response:
                if response.status == 200:
                    return {
                        "status": "healthy",
                        "provider": self.config.provider.value,
                        "model": self.config.model_name,
                        "metrics": {
                            "total_requests": self._metrics.total_requests,
                            "average_response_time": self._metrics.average_response_time,
                        },
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "provider": self.config.provider.value,
                        "error": f"API returned status {response.status}",
                    }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "provider": self.config.provider.value,
                "error": str(e),
            }


class RateLimiter:
    """Rate limiter for AI API requests."""

    def __init__(self, rpm: int = 60, tpm: int = 90000):
        """Initialize rate limiter.

        Args:
            rpm: Requests per minute limit.
            tpm: Tokens per minute limit.
        """
        self.rpm = rpm
        self.tpm = tpm
        self._request_times: List[float] = []
        self._token_counts: List[Tuple[float, int]] = []
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 0) -> None:
        """Acquire rate limit permit.

        Args:
            tokens: Number of tokens for this request.

        Raises:
            AIRateLimitError: If rate limit exceeded.
        """
        async with self._lock:
            now = asyncio.get_event_loop().time()
            self._cleanup(now)

            if len(self._request_times) >= self.rpm:
                wait_time = self._request_times[0] + 60 - now
                if wait_time > 0:
                    raise AIRateLimitError(
                        f"Rate limit exceeded. Wait {wait_time:.1f}s"
                    )

            if tokens > 0:
                total_tokens = sum(t for _, t in self._token_counts)
                if total_tokens + tokens > self.tpm:
                    raise AIRateLimitError("Token rate limit exceeded")

            self._request_times.append(now)
            if tokens > 0:
                self._token_counts.append((now, tokens))

    def _cleanup(self, now: float) -> None:
        """Remove expired entries from tracking.

        Args:
            now: Current timestamp.
        """
        cutoff = now - 60
        self._request_times = [t for t in self._request_times if t > cutoff]
        self._token_counts = [(t, c) for t, c in self._token_counts if t > cutoff]