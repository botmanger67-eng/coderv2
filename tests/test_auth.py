"""
Unit tests for authorization module.

This module contains comprehensive tests for the authentication and authorization
functionality, including token validation, permission checks, and role-based access control.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock

from src.auth import (
    AuthManager,
    TokenValidator,
    PermissionChecker,
    AuthError,
    TokenExpiredError,
    InvalidTokenError,
    InsufficientPermissionsError,
    UserRole,
    Permission,
    AuthConfig,
    TokenPayload,
    AuthResult,
)


class TestAuthManager:
    """Test suite for AuthManager class."""

    @pytest.fixture
    def auth_config(self) -> AuthConfig:
        """Fixture providing default auth configuration."""
        return AuthConfig(
            secret_key="test-secret-key-12345",
            token_expiry_minutes=30,
            refresh_token_expiry_days=7,
            algorithm="HS256",
            allowed_roles=[UserRole.ADMIN, UserRole.USER, UserRole.VIEWER],
        )

    @pytest.fixture
    def auth_manager(self, auth_config: AuthConfig) -> AuthManager:
        """Fixture providing AuthManager instance."""
        return AuthManager(config=auth_config)

    @pytest.fixture
    def valid_user_payload(self) -> Dict[str, Any]:
        """Fixture providing valid user payload for token generation."""
        return {
            "user_id": "usr_12345",
            "username": "john_doe",
            "role": UserRole.USER,
            "permissions": [Permission.READ, Permission.WRITE],
            "email": "john@example.com",
        }

    def test_initialization_with_valid_config(self, auth_config: AuthConfig) -> None:
        """Test AuthManager initialization with valid configuration."""
        manager = AuthManager(config=auth_config)
        assert manager.config == auth_config
        assert manager.token_validator is not None
        assert manager.permission_checker is not None

    def test_initialization_with_invalid_config(self) -> None:
        """Test AuthManager initialization with invalid configuration."""
        with pytest.raises(ValueError, match="Secret key cannot be empty"):
            AuthManager(config=AuthConfig(secret_key=""))

    def test_generate_token_success(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test successful token generation."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT format check

    def test_generate_token_with_expiry(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test token generation with custom expiry time."""
        custom_expiry = timedelta(hours=2)
        token = auth_manager.generate_token(
            user_data=valid_user_payload, expiry=custom_expiry
        )
        decoded = auth_manager.validate_token(token)
        assert decoded is not None
        assert decoded.expiry > datetime.utcnow() + timedelta(hours=1)

    def test_generate_token_missing_required_fields(
        self, auth_manager: AuthManager
    ) -> None:
        """Test token generation with missing required fields."""
        with pytest.raises(ValueError, match="Missing required field"):
            auth_manager.generate_token(user_data={"username": "test"})

    def test_validate_token_success(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test successful token validation."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        result = auth_manager.validate_token(token)
        assert result is not None
        assert result.user_id == valid_user_payload["user_id"]
        assert result.role == valid_user_payload["role"]
        assert result.is_valid is True

    def test_validate_token_expired(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test validation of expired token."""
        expired_payload = valid_user_payload.copy()
        expired_payload["exp"] = datetime.utcnow() - timedelta(hours=1)
        token = auth_manager.generate_token(user_data=expired_payload)
        
        with pytest.raises(TokenExpiredError, match="Token has expired"):
            auth_manager.validate_token(token)

    def test_validate_token_invalid_signature(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test validation of token with invalid signature."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        tampered_token = token[:-5] + "XXXXX"
        
        with pytest.raises(InvalidTokenError, match="Invalid token signature"):
            auth_manager.validate_token(tampered_token)

    def test_validate_token_malformed(self, auth_manager: AuthManager) -> None:
        """Test validation of malformed token."""
        with pytest.raises(InvalidTokenError, match="Malformed token"):
            auth_manager.validate_token("not-a-valid-token")

    def test_refresh_token_success(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test successful token refresh."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        refresh_token = auth_manager.generate_refresh_token(user_data=valid_user_payload)
        
        new_token, new_refresh_token = auth_manager.refresh_token(
            token=token, refresh_token=refresh_token
        )
        
        assert new_token != token
        assert new_refresh_token != refresh_token
        decoded = auth_manager.validate_token(new_token)
        assert decoded.user_id == valid_user_payload["user_id"]

    def test_refresh_token_with_expired_refresh(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test refresh with expired refresh token."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        expired_refresh = auth_manager.generate_refresh_token(
            user_data=valid_user_payload, 
            expiry=timedelta(days=-1)
        )
        
        with pytest.raises(TokenExpiredError, match="Refresh token has expired"):
            auth_manager.refresh_token(token=token, refresh_token=expired_refresh)

    def test_revoke_token(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test token revocation."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        auth_manager.revoke_token(token)
        
        with pytest.raises(InvalidTokenError, match="Token has been revoked"):
            auth_manager.validate_token(token)

    def test_check_permission_success(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test successful permission check."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        result = auth_manager.check_permission(
            token=token, required_permission=Permission.READ
        )
        assert result is True

    def test_check_permission_insufficient(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test permission check with insufficient permissions."""
        viewer_payload = valid_user_payload.copy()
        viewer_payload["permissions"] = [Permission.READ]
        token = auth_manager.generate_token(user_data=viewer_payload)
        
        with pytest.raises(InsufficientPermissionsError, match="Insufficient permissions"):
            auth_manager.check_permission(
                token=token, required_permission=Permission.DELETE
            )

    def test_check_role_success(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test successful role check."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        result = auth_manager.check_role(token=token, required_role=UserRole.USER)
        assert result is True

    def test_check_role_insufficient(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test role check with insufficient role."""
        viewer_payload = valid_user_payload.copy()
        viewer_payload["role"] = UserRole.VIEWER
        token = auth_manager.generate_token(user_data=viewer_payload)
        
        with pytest.raises(InsufficientPermissionsError, match="Insufficient role"):
            auth_manager.check_role(token=token, required_role=UserRole.ADMIN)

    def test_get_user_from_token(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test extracting user information from token."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        user = auth_manager.get_user_from_token(token)
        
        assert user.user_id == valid_user_payload["user_id"]
        assert user.username == valid_user_payload["username"]
        assert user.role == valid_user_payload["role"]

    def test_authenticate_success(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test successful authentication flow."""
        result = auth_manager.authenticate(
            username="john_doe", password="correct_password"
        )
        assert result.success is True
        assert result.token is not None
        assert result.refresh_token is not None

    def test_authenticate_failure(
        self, auth_manager: AuthManager
    ) -> None:
        """Test authentication failure."""
        result = auth_manager.authenticate(
            username="john_doe", password="wrong_password"
        )
        assert result.success is False
        assert result.token is None
        assert result.error is not None

    def test_concurrent_token_validation(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test concurrent token validation for performance."""
        import concurrent.futures
        
        tokens = [
            auth_manager.generate_token(user_data=valid_user_payload)
            for _ in range(10)
        ]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(auth_manager.validate_token, tokens))
        
        assert all(result is not None for result in results)

    def test_token_blacklist_cleanup(
        self, auth_manager: AuthManager, valid_user_payload: Dict[str, Any]
    ) -> None:
        """Test automatic cleanup of expired tokens from blacklist."""
        token = auth_manager.generate_token(user_data=valid_user_payload)
        auth_manager.revoke_token(token)
        
        # Simulate time passing
        with patch.object(auth_manager, '_get_current_time', return_value=datetime.utcnow() + timedelta(days=30)):
            auth_manager._cleanup_blacklist()
            assert token not in auth_manager._blacklist


class TestTokenValidator:
    """Test suite for TokenValidator class."""

    @pytest.fixture
    def validator(self, auth_config: AuthConfig) -> TokenValidator:
        """Fixture providing TokenValidator instance."""
        return TokenValidator(config=auth_config)

    def test_validate_token_structure_valid(self, validator: TokenValidator) -> None:
        """Test validation of token structure."""
        valid_token = "header.payload.signature"
        assert validator._validate_structure(valid_token) is True

    def test_validate_token_structure_invalid(self, validator: TokenValidator) -> None:
        """Test validation of invalid token structure."""
        invalid_tokens = ["", "no-dots", "too.many.dots.here"]
        for token in invalid_tokens:
            assert validator._validate_structure(token) is False

    def test_decode_payload_valid(self, validator: TokenValidator) -> None:
        """Test decoding of valid token payload."""
        payload = {"user_id": "test", "exp": datetime.utcnow().timestamp() + 3600}
        token = validator._encode_payload(payload)
        decoded = validator._decode_payload(token)
        assert decoded["user_id"] == "test"

    def test_decode_payload_invalid(self, validator: TokenValidator) -> None:
        """Test decoding of invalid token payload."""
        with pytest.raises(InvalidTokenError):
            validator._decode_payload("invalid.token.data")


class TestPermissionChecker:
    """Test suite for PermissionChecker class."""

    @pytest.fixture
    def permission_checker(self, auth_config: AuthConfig) -> PermissionChecker:
        """Fixture providing PermissionChecker instance."""
        return PermissionChecker(config=auth_config)

    def test_check_permission_hierarchy(
        self, permission_checker: PermissionChecker
    ) -> None:
        """Test permission hierarchy checking."""
        admin_permissions = [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN]
        user_permissions = [Permission.READ, Permission.WRITE]
        viewer_permissions = [Permission.READ]
        
        assert permission_checker.has_permission(admin_permissions, Permission.ADMIN) is True
        assert permission_checker.has_permission(user_permissions, Permission.DELETE) is False
        assert permission_checker.has_permission(viewer_permissions, Permission.WRITE) is False

    def test_check_role_hierarchy(
        self, permission_checker: PermissionChecker
    ) -> None:
        """Test role hierarchy checking."""
        assert permission_checker.has_role(UserRole.ADMIN, UserRole.ADMIN) is True
        assert permission_checker.has_role(UserRole.ADMIN, UserRole.USER) is True
        assert permission_checker.has_role(UserRole.USER, UserRole.ADMIN) is False

    def test_get_required_permissions_for_role(
        self, permission_checker: PermissionChecker
    ) -> None:
        """Test getting required permissions for a role."""
        admin_perms = permission_checker.get_permissions_for_role(UserRole.ADMIN)
        assert Permission.ADMIN in admin_perms
        
        viewer_perms = permission_checker.get_permissions_for_role(UserRole.VIEWER)
        assert Permission.ADMIN not in viewer_perms


class TestAuthErrorHandling:
    """Test suite for authentication error handling."""

    def test_auth_error_creation(self) -> None:
        """Test AuthError creation."""
        error = AuthError("Test error", status_code=401)
        assert str(error) == "Test error"
        assert error.status_code == 401

    def test_token_expired_error(self) -> None:
        """Test TokenExpiredError creation."""
        error = TokenExpiredError("Token expired")
        assert isinstance(error, AuthError)
        assert error.status_code == 401

    def test_invalid_token_error(self) -> None:
        """Test InvalidTokenError creation."""
        error = InvalidTokenError("Invalid token")
        assert isinstance(error, AuthError)
        assert error.status_code == 401

    def test_insufficient_permissions_error(self) -> None:
        """Test InsufficientPermissionsError creation."""
        error = InsufficientPermissionsError("Insufficient permissions")
        assert isinstance(error, AuthError)
        assert error.status_code == 403


class TestAuthConfig:
    """Test suite for AuthConfig class."""

    def test_default_config_values(self) -> None:
        """Test default configuration values."""
        config = AuthConfig(secret_key="test-key")
        assert config.token_expiry_minutes == 30
        assert config.refresh_token_expiry_days == 7
        assert config.algorithm == "HS256"

    def test_config_validation(self) -> None:
        """Test configuration validation."""
        with pytest.raises(ValueError, match="Invalid token expiry"):
            AuthConfig(secret_key="test", token_expiry_minutes=-1)

        with pytest.raises(ValueError, match="Invalid algorithm"):
            AuthConfig(secret_key="test", algorithm="invalid")

    def test_config_serialization(self) -> None:
        """Test configuration serialization."""
        config = AuthConfig(secret_key="test-key")
        serialized = config.to_dict()
        assert isinstance(serialized, dict)
        assert "secret_key" in serialized
        assert serialized["algorithm"] == "HS256"


class TestTokenPayload:
    """Test suite for TokenPayload class."""

    def test_payload_creation(self) -> None:
        """Test TokenPayload creation."""
        payload = TokenPayload(
            user_id="usr_123",
            username="test_user",
            role=UserRole.USER,
            permissions=[Permission.READ],
            email="test@example.com",
            exp=datetime.utcnow() + timedelta(hours=1),
            iat=datetime.utcnow(),
        )
        assert payload.user_id == "usr_123"
        assert payload.is_valid is True

    def test_payload_expiry_check(self) -> None:
        """Test payload expiry checking."""
        expired_payload = TokenPayload(
            user_id="usr_123",
            username="test_user",
            role=UserRole.USER,
            permissions=[Permission.READ],
            email="test@example.com",
            exp=datetime.utcnow() - timedelta(hours=1),
            iat=datetime.utcnow() - timedelta(hours=2),
        )
        assert expired_payload.is_expired is True
        assert expired_payload.is_valid is False


class TestAuthResult:
    """Test suite for AuthResult class."""

    def test_successful_auth_result(self) -> None:
        """Test successful authentication result."""
        result = AuthResult(
            success=True,
            token="valid_token",
            refresh_token="valid_refresh",
            user_id="usr_123",
            role=UserRole.USER,
        )
        assert result.success is True
        assert result.error is None

    def test_failed_auth_result(self) -> None:
        """Test failed authentication result."""
        result = AuthResult(
            success=False,
            error="Invalid credentials",
        )
        assert result.success is False
        assert result.token is None
        assert result.refresh_token is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.auth", "--cov-report=term-missing"])