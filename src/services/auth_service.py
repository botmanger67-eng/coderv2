"""
Authentication service module providing user authentication, token management,
and session handling with enterprise-grade security features.
"""

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from enum import Enum

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.models.user import User, UserRole
from src.repositories.user_repository import UserRepository
from src.config.settings import Settings
from src.utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    TokenExpiredError,
    UserNotFoundError,
    InvalidCredentialsError,
    AccountLockedError,
    PasswordPolicyError,
    MFARequiredError,
    SessionExpiredError
)
from src.utils.logging import get_logger
from src.utils.validators import validate_email, validate_password_strength

logger = get_logger(__name__)


class TokenType(Enum):
    """Enumeration of supported token types."""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"
    MFA = "mfa"


class AuthProvider(Enum):
    """Enumeration of supported authentication providers."""
    LOCAL = "local"
    LDAP = "ldap"
    OAUTH2 = "oauth2"
    SAML = "saml"


class MFAMethod(Enum):
    """Enumeration of supported multi-factor authentication methods."""
    TOTP = "totp"
    SMS = "sms"
    EMAIL = "email"
    HARDWARE_KEY = "hardware_key"


class AuthService:
    """
    Enterprise-grade authentication service implementing secure user authentication,
    token management, session handling, and multi-factor authentication support.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        settings: Settings,
        encryption_key: Optional[bytes] = None
    ) -> None:
        """
        Initialize the authentication service.

        Args:
            user_repository: Repository for user data access
            settings: Application configuration settings
            encryption_key: Optional encryption key for token encryption
        """
        self._user_repository = user_repository
        self._settings = settings
        self._fernet = Fernet(encryption_key or Fernet.generate_key())
        self._failed_attempts: Dict[str, List[datetime]] = {}
        self._active_sessions: Dict[str, Dict] = {}
        self._mfa_secrets: Dict[str, str] = {}

    def authenticate(
        self,
        username: str,
        password: str,
        provider: AuthProvider = AuthProvider.LOCAL,
        mfa_code: Optional[str] = None
    ) -> Tuple[str, str, User]:
        """
        Authenticate a user with username and password.

        Args:
            username: User's username or email
            password: User's password
            provider: Authentication provider
            mfa_code: Optional MFA verification code

        Returns:
            Tuple containing (access_token, refresh_token, user)

        Raises:
            InvalidCredentialsError: If credentials are invalid
            AccountLockedError: If account is locked
            MFARequiredError: If MFA verification is required
            AuthenticationError: If authentication fails
        """
        try:
            self._check_account_lockout(username)

            user = self._user_repository.find_by_username(username)
            if not user:
                user = self._user_repository.find_by_email(username)

            if not user:
                self._record_failed_attempt(username)
                raise InvalidCredentialsError("Invalid username or password")

            if not user.is_active:
                raise AccountLockedError("Account is deactivated")

            if not self._verify_password(password, user.password_hash):
                self._record_failed_attempt(username)
                raise InvalidCredentialsError("Invalid username or password")

            if user.mfa_enabled and not mfa_code:
                raise MFARequiredError("MFA verification required")

            if mfa_code and not self._verify_mfa_code(user, mfa_code):
                raise AuthenticationError("Invalid MFA code")

            self._clear_failed_attempts(username)

            access_token = self._generate_access_token(user)
            refresh_token = self._generate_refresh_token(user)

            self._create_session(user.id, access_token, refresh_token)

            logger.info(
                "User authenticated successfully",
                extra={
                    "user_id": user.id,
                    "username": user.username,
                    "provider": provider.value
                }
            )

            return access_token, refresh_token, user

        except (InvalidCredentialsError, AccountLockedError, MFARequiredError):
            raise
        except Exception as error:
            logger.error(
                "Authentication failed",
                extra={
                    "username": username,
                    "error": str(error)
                }
            )
            raise AuthenticationError(f"Authentication failed: {str(error)}")

    def authenticate_with_token(
        self,
        access_token: str,
        token_type: TokenType = TokenType.ACCESS
    ) -> User:
        """
        Authenticate a user using an access token.

        Args:
            access_token: JWT access token
            token_type: Type of token to validate

        Returns:
            Authenticated User object

        Raises:
            InvalidTokenError: If token is invalid
            TokenExpiredError: If token has expired
            AuthenticationError: If authentication fails
        """
        try:
            payload = self._decode_token(access_token, token_type)

            if payload.get("type") != token_type.value:
                raise InvalidTokenError("Invalid token type")

            user_id = payload.get("sub")
            if not user_id:
                raise InvalidTokenError("Invalid token payload")

            user = self._user_repository.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            if not user.is_active:
                raise AccountLockedError("Account is deactivated")

            session_id = payload.get("session_id")
            if session_id and session_id not in self._active_sessions:
                raise SessionExpiredError("Session has expired")

            if session_id:
                session = self._active_sessions[session_id]
                if session.get("access_token") != access_token:
                    raise InvalidTokenError("Token does not match session")

            logger.debug(
                "Token authentication successful",
                extra={"user_id": user.id, "token_type": token_type.value}
            )

            return user

        except (InvalidTokenError, TokenExpiredError, SessionExpiredError):
            raise
        except Exception as error:
            logger.error(
                "Token authentication failed",
                extra={"error": str(error)}
            )
            raise AuthenticationError(f"Token authentication failed: {str(error)}")

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, str]:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            Tuple containing (new_access_token, new_refresh_token)

        Raises:
            InvalidTokenError: If refresh token is invalid
            TokenExpiredError: If refresh token has expired
            AuthenticationError: If refresh fails
        """
        try:
            payload = self._decode_token(refresh_token, TokenType.REFRESH)

            user_id = payload.get("sub")
            if not user_id:
                raise InvalidTokenError("Invalid refresh token payload")

            user = self._user_repository.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            if not user.is_active:
                raise AccountLockedError("Account is deactivated")

            session_id = payload.get("session_id")
            if session_id and session_id not in self._active_sessions:
                raise SessionExpiredError("Session has expired")

            new_access_token = self._generate_access_token(user)
            new_refresh_token = self._generate_refresh_token(user)

            if session_id:
                self._active_sessions[session_id]["access_token"] = new_access_token
                self._active_sessions[session_id]["refresh_token"] = new_refresh_token

            logger.info(
                "Access token refreshed",
                extra={"user_id": user.id}
            )

            return new_access_token, new_refresh_token

        except (InvalidTokenError, TokenExpiredError, SessionExpiredError):
            raise
        except Exception as error:
            logger.error(
                "Token refresh failed",
                extra={"error": str(error)}
            )
            raise AuthenticationError(f"Token refresh failed: {str(error)}")

    def logout(self, access_token: str) -> None:
        """
        Logout a user by invalidating their session.

        Args:
            access_token: Current access token

        Raises:
            InvalidTokenError: If token is invalid
            AuthenticationError: If logout fails
        """
        try:
            payload = self._decode_token(access_token, TokenType.ACCESS)
            session_id = payload.get("session_id")

            if session_id and session_id in self._active_sessions:
                del self._active_sessions[session_id]
                logger.info(
                    "User logged out",
                    extra={"user_id": payload.get("sub")}
                )
            else:
                logger.warning(
                    "Logout attempted with invalid session",
                    extra={"token_sub": payload.get("sub")}
                )

        except Exception as error:
            logger.error(
                "Logout failed",
                extra={"error": str(error)}
            )
            raise AuthenticationError(f"Logout failed: {str(error)}")

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password with validation.

        Args:
            user_id: User identifier
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password was changed successfully

        Raises:
            UserNotFoundError: If user not found
            InvalidCredentialsError: If current password is incorrect
            PasswordPolicyError: If new password doesn't meet policy
            AuthenticationError: If password change fails
        """
        try:
            user = self._user_repository.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            if not self._verify_password(current_password, user.password_hash):
                raise InvalidCredentialsError("Current password is incorrect")

            if not validate_password_strength(new_password):
                raise PasswordPolicyError(
                    "Password does not meet security requirements"
                )

            if current_password == new_password:
                raise PasswordPolicyError(
                    "New password must be different from current password"
                )

            new_password_hash = self._hash_password(new_password)
            user.password_hash = new_password_hash
            user.password_changed_at = datetime.utcnow()
            user.password_history = self._update_password_history(
                user.password_history,
                new_password_hash
            )

            self._user_repository.update(user)

            self._invalidate_user_sessions(user_id)

            logger.info(
                "Password changed successfully",
                extra={"user_id": user_id}
            )

            return True

        except (UserNotFoundError, InvalidCredentialsError, PasswordPolicyError):
            raise
        except Exception as error:
            logger.error(
                "Password change failed",
                extra={"user_id": user_id, "error": str(error)}
            )
            raise AuthenticationError(f"Password change failed: {str(error)}")

    def reset_password(
        self,
        reset_token: str,
        new_password: str
    ) -> bool:
        """
        Reset password using a valid reset token.

        Args:
            reset_token: Password reset token
            new_password: New password to set

        Returns:
            True if password was reset successfully

        Raises:
            InvalidTokenError: If reset token is invalid
            TokenExpiredError: If reset token has expired
            PasswordPolicyError: If new password doesn't meet policy
            AuthenticationError: If password reset fails
        """
        try:
            payload = self._decode_token(
                reset_token,
                TokenType.RESET_PASSWORD
            )

            user_id = payload.get("sub")
            if not user_id:
                raise InvalidTokenError("Invalid reset token payload")

            user = self._user_repository.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            if not validate_password_strength(new_password):
                raise PasswordPolicyError(
                    "Password does not meet security requirements"
                )

            new_password_hash = self._hash_password(new_password)
            user.password_hash = new_password_hash
            user.password_changed_at = datetime.utcnow()
            user.password_history = self._update_password_history(
                user.password_history,
                new_password_hash
            )

            self._user_repository.update(user)

            self._invalidate_user_sessions(user_id)

            logger.info(
                "Password reset successfully",
                extra={"user_id": user_id}
            )

            return True

        except (InvalidTokenError, TokenExpiredError, PasswordPolicyError):
            raise
        except Exception as error:
            logger.error(
                "Password reset failed",
                extra={"error": str(error)}
            )
            raise AuthenticationError(f"Password reset failed: {str(error)}")

    def generate_reset_token(self, email: str) -> str:
        """
        Generate a password reset token for the given email.

        Args:
            email: User's email address

        Returns:
            Password reset token string

        Raises:
            UserNotFoundError: If email not found
            AuthenticationError: If token generation fails
        """
        try:
            user = self._user_repository.find_by_email(email)
            if not user:
                raise UserNotFoundError(f"Email {email} not found")

            reset_token = self._generate_token(
                user,
                TokenType.RESET_PASSWORD,
                expiration_minutes=self._settings.reset_token_expiry_minutes
            )

            logger.info(
                "Reset token generated",
                extra={"user_id": user.id, "email": email}
            )

            return reset_token

        except UserNotFoundError:
            raise
        except Exception as error:
            logger.error(
                "Reset token generation failed",
                extra={"email": email, "error": str(error)}
            )
            raise AuthenticationError(
                f"Reset token generation failed: {str(error)}"
            )

    def verify_email(self, verification_token: str) -> bool:
        """
        Verify user's email address using verification token.

        Args:
            verification_token: Email verification token

        Returns:
            True if email was verified successfully

        Raises:
            InvalidTokenError: If verification token is invalid
            TokenExpiredError: If verification token has expired
            AuthenticationError: If verification fails
        """
        try:
            payload = self._decode_token(
                verification_token,
                TokenType.EMAIL_VERIFICATION
            )

            user_id = payload.get("sub")
            if not user_id:
                raise InvalidTokenError("Invalid verification token payload")

            user = self._user_repository.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            user.email_verified = True
            self._user_repository.update(user)

            logger.info(
                "Email verified successfully",
                extra={"user_id": user_id}
            )

            return True

        except (InvalidTokenError, TokenExpiredError):
            raise
        except Exception as error:
            logger.error(
                "Email verification failed",
                extra={"error": str(error)}
            )
            raise AuthenticationError(
                f"Email verification failed: {str(error)}"
            )

    def setup_mfa(
        self,
        user_id: str,
        method: MFAMethod = MFAMethod.TOTP
    ) -> Dict[str, str]:
        """
        Set up multi-factor authentication for a user.

        Args:
            user_id: User identifier
            method: MFA method to set up

        Returns:
            Dictionary containing MFA setup information

        Raises:
            UserNotFoundError: If user not found
            AuthenticationError: If MFA setup fails
        """
        try:
            user = self._user_repository.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            if method == MFAMethod.TOTP:
                secret = self._generate_totp_secret()
                self._mfa_secrets[user_id] = secret

                setup_data = {
                    "method": method.value,
                    "secret": secret,
                    "qr_code_url": self._generate_totp_qr_url(
                        user.username,
                        secret
                    )
                }
            elif method == MFAMethod.SMS:
                setup_data = {
                    "method": method.value,
                    "phone": user.phone_number,
                    "message": "MFA setup initiated"
                }
            elif method == MFAMethod.EMAIL:
                setup_data = {
                    "method": method.value,
                    "email": user.email,
                    "message": "MFA setup initiated"
                }
            else:
                raise AuthenticationError(f"Unsupported MFA method: {method.value}")

            user.mfa_enabled = True
            user.mfa_method = method.value
            self._user_repository.update(user)

            logger.info(
                "MFA setup completed",
                extra={"user_id": user_id, "method": method.value}
            )

            return setup_data

        except UserNotFoundError:
            raise
        except Exception as error:
            logger.error(
                "MFA setup failed",
                extra={"user_id": user_id, "error": str(error)}
            )
            raise AuthenticationError(f"MFA setup failed: {str(error)}")

    def disable_mfa(self, user_id: str) -> bool:
        """
        Disable multi-factor authentication for a user.

        Args:
            user_id: User identifier

        Returns:
            True if MFA was disabled successfully

        Raises:
            UserNotFoundError: If user not found
            AuthenticationError: If MFA disable fails
        """
        try:
            user = self._user_repository.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            user.mfa_enabled = False
            user.mfa_method = None
            self._user_repository.update(user)

            if user_id in self._mfa_secrets:
                del self._mfa_secrets[user_id]

            logger.info(
                "MFA disabled",
                extra={"user_id": user_id}
            )

            return True

        except UserNotFoundError:
            raise
        except Exception as error:
            logger.error(
                "MFA disable failed",
                extra={"user_id": user_id, "error": str(error)}
            )
            raise AuthenticationError(f"MFA disable failed: {str(error)}")

    def validate_session(self, session_id: str) -> bool:
        """
        Validate if a session is still active.

        Args:
            session_id: Session identifier

        Returns:
            True if session is valid and active
        """
        try:
            if session_id not in self._active_sessions:
                return False

            session = self._active_sessions[session_id]
            expires_at = session.get("expires_at")

            if expires_at and datetime.utcnow() > expires_at:
                del self._active_sessions[session_id]
                return False

            return True

        except Exception as error:
            logger.error(
                "Session validation failed",
                extra={"session_id": session_id, "error": str(error)}
            )
            return False

    def get_active_sessions(self, user_id: str) -> List[Dict]:
        """
        Get all active sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of active session dictionaries
        """
        try:
            active_sessions = []
            for session_id, session_data in self._active_sessions.items():
                if session_data.get("user_id") == user_id:
                    if self.validate_session(session_id):
                        active_sessions.append({
                            "session_id": session_id,
                            "created_at": session_data.get("created_at"),
                            "expires_at": session_data.get("expires_at"),
                            "ip_address": session_data.get("ip_address"),
                            "user_agent": session_data.get("user_agent")
                        })

            return active_sessions

        except Exception as error:
            logger.error(
                "Failed to get active sessions",
                extra={"user_id": user_id, "error": str(error)}
            )
            return []

    def revoke_session(self, session_id: str) -> bool:
        """
        Revoke a specific session.

        Args:
            session_id: Session identifier to revoke

        Returns:
            True if session was revoked successfully
        """
        try:
            if session_id in self._active_sessions:
                del self._active_sessions[session_id]
                logger.info(
                    "Session revoked",
                    extra={"session_id": session_id}
                )
                return True

            logger.warning(
                "Session not found for revocation",
                extra={"session_id": session_id}
            )
            return False

        except Exception as error:
            logger.error(
                "Session revocation failed",
                extra={"session_id": session_id, "error": str(error)}
            )
            return False

    def _generate_access_token(self, user: User) -> str:
        """Generate a JWT access token for the user."""
        return self._generate_token(
            user,
            TokenType.ACCESS,
            expiration_minutes=self._settings.access_token_expiry_minutes
        )

    def _generate_refresh_token(self, user: User) -> str:
        """Generate a JWT refresh token for the user."""
        return self._generate_token(
            user,
            TokenType.REFRESH,
            expiration_minutes=self._settings.refresh_token_expiry_minutes
        )

    def _generate_token(
        self,
        user: User,
        token_type: TokenType,
        expiration_minutes: int
    ) -> str:
        """
        Generate a JWT token with specified type and expiration.

        Args:
            user: User object
            token_type: Type of token to generate
            expiration_minutes: Token expiration in minutes

        Returns:
            Encoded JWT token string
        """
        now = datetime.utcnow()
        payload = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "type": token_type.value,
            "iat": now,
            "exp": now + timedelta(minutes=expiration_minutes),
            "jti": secrets.token_hex(16),
            "session_id": secrets.token_hex(32)
        }

        if token_type == TokenType.ACCESS:
            payload["permissions"] = self._get_user_permissions(user)

        token = jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm
        )

        return token

    def _decode_token(
        self,
        token: str,
        expected_type: TokenType
    ) -> Dict:
        """
        Decode and validate a JWT token.

        Args:
            token: JWT token string
            expected_type: Expected token type

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is invalid
            TokenExpiredError: If token has expired
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm]
            )

            if payload.get("type") != expected_type.value:
                raise InvalidTokenError(
                    f"Expected token type {expected_type.value}, "
                    f"got {payload.get('type')}"
                )

            return payload

        except jwt.ExpiredSignatureError as error:
            raise TokenExpiredError(f"Token has expired: {str(error)}")
        except jwt.InvalidTokenError as error:
            raise InvalidTokenError(f"Invalid token: {str(error)}")

    def _hash_password(self, password: str) -> str:
        """
        Hash a password using PBKDF2 with SHA-256.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        salt = secrets.token_hex(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=self._settings.password_hash_iterations
        )
        key = kdf.derive(password.encode())
        return f"{salt}:{key.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Plain text password to verify
            password_hash: Stored password hash

        Returns:
            True if password matches hash
        """
        try:
            salt, key_hex = password_hash.split(":")
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=self._settings.password_hash_iterations
            )
            kdf.verify(password.encode(), bytes.fromhex(key_hex))
            return True
        except Exception:
            return False

    def _generate_totp_secret(self) -> str:
        """Generate a TOTP secret key."""
        return secrets.token_hex(20)

    def _generate_totp_qr_url(self, username: str, secret: str) -> str:
        """Generate a QR code URL for TOTP setup."""
        import urllib.parse
        issuer = urllib.parse.quote(self._settings.app_name)
        encoded_username = urllib.parse.quote(username)
        return f"otpauth://totp/{issuer}:{encoded_username}?secret={secret}&issuer={issuer}"

    def _verify_mfa_code(self, user: User, code: str) -> bool:
        """
        Verify an MFA code for the user.

        Args:
            user: User object
            code: MFA verification code

        Returns:
            True if code is valid
        """
        try:
            if user.mfa_method == MFAMethod.TOTP.value:
                import pyotp
                secret = self._mfa_secrets.get(user.id)
                if not secret:
                    return False
                totp = pyotp.TOTP(secret)
                return totp.verify(code, valid_window=1)
            else:
                # Implement other MFA methods as needed
                return False

        except Exception as error:
            logger.error(
                "MFA verification failed",
                extra={"user_id": user.id, "error": str(error)}
            )
            return False

    def _get_user_permissions(self, user: User) -> List[str]:
        """
        Get permissions for a user based on their role.

        Args:
            user: User object

        Returns:
            List of permission strings
        """
        permissions = {
            UserRole.ADMIN: [
                "users:read", "users:write", "users:delete",
                "roles:manage", "settings:read", "settings:write",
                "audit:read", "reports:read"
            ],
            UserRole.MANAGER: [
                "users:read", "users:write",
                "reports:read", "reports:write"
            ],
            UserRole.USER: [
                "profile:read", "profile:write"
            ],
            UserRole.VIEWER: [
                "reports:read"
            ]
        }

        return permissions.get(user.role, [])

    def _create_session(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str
    ) -> str:
        """
        Create a new session for the user.

        Args:
            user_id: User identifier
            access_token: JWT access token
            refresh_token: JWT refresh token

        Returns:
            Session identifier
        """
        session_id = secrets.token_hex(32)
        self._active_sessions[session_id] = {
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(
                minutes=self._settings.session_expiry_minutes
            ),
            "ip_address": None,
            "user_agent": None
        }

        return session_id

    def _invalidate_user_sessions(self, user_id: str) -> None:
        """
        Invalidate all sessions for a user.

        Args:
            user_id: User identifier
        """
        sessions_to_remove = []
        for session_id, session_data in self._active_sessions.items():
            if session_data.get("user_id") == user_id:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self._active_sessions[session_id]

        logger.info(
            "User sessions invalidated",
            extra={"user_id": user_id, "sessions_removed": len(sessions_to_remove)}
        )

    def _check_account_lockout(self, username: str) -> None:
        """
        Check if an account is locked due to too many failed attempts.

        Args:
            username: Username to check

        Raises:
            AccountLockedError: If account is locked
        """
        attempts = self._failed_attempts.get(username, [])
        recent_attempts = [
            attempt for attempt in attempts
            if datetime.utcnow() - attempt < timedelta(
                minutes=self._settings.lockout_window_minutes
            )
        ]

        if len(recent_attempts) >= self._settings.max_failed_attempts:
            raise AccountLockedError(
                f"Account locked due to {self._settings.max_failed_attempts} "
                f"failed login attempts. Try again in "
                f"{self._settings.lockout_window_minutes} minutes."
            )

    def _record_failed_attempt(self, username: str) -> None:
        """
        Record a failed authentication attempt.

        Args:
            username: Username that failed authentication
        """
        if username not in self._failed_attempts:
            self._failed_attempts[username] = []
        self._failed_attempts[username].append(datetime.utcnow())

        logger.warning(
            "Failed authentication attempt recorded",
            extra={
                "username": username,
                "attempt_count": len(self._failed_attempts[username])
            }
        )

    def _clear_failed_attempts(self, username: str) -> None:
        """
        Clear failed authentication attempts for a user.

        Args:
            username: Username to clear attempts for
        """
        if username in self._failed_attempts:
            del self._failed_attempts[username]

    def _update_password_history(
        self,
        password_history: List[str],
        new_password_hash: str
    ) -> List[str]:
        """
        Update password history with new hash.

        Args:
            password_history: List of previous password hashes
            new_password_hash: New password hash to add

        Returns:
            Updated password history list
        """
        if password_history is None:
            password_history = []

        password_history.append(new_password_hash)

        # Keep only the last N password hashes
        max_history = self._settings.password_history_count
        if len(password_history) > max_history:
            password_history = password_history[-max_history:]

        return password_history

    def __repr__(self) -> str:
        """Return string representation of AuthService."""
        return (
            f"AuthService("
            f"user_repository={self._user_repository}, "
            f"settings={self._settings}"
            f")"
        )