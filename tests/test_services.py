"""
Unit tests for service layer.

This module contains comprehensive tests for all service functions,
covering success scenarios, error cases, and edge conditions.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from app.services import (
    create_user,
    get_user,
    update_user,
    delete_user,
    list_users,
    authenticate_user,
    generate_token,
    validate_token,
    revoke_token,
    send_notification,
    process_payment,
    calculate_metrics,
)
from app.models import User, Token, Notification, Payment
from app.exceptions import (
    ServiceError,
    NotFoundError,
    AuthenticationError,
    ValidationError,
    DuplicateResourceError,
    PaymentError,
    NotificationError,
)
from app.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    TokenResponse,
    NotificationRequest,
    PaymentRequest,
    MetricsResponse,
)


class TestUserService:
    """Test suite for user-related service functions."""

    @pytest.fixture
    def mock_user_repository(self) -> Mock:
        """Create a mock user repository."""
        return Mock()

    @pytest.fixture
    def mock_token_service(self) -> Mock:
        """Create a mock token service."""
        return Mock()

    @pytest.fixture
    def sample_user_data(self) -> Dict[str, Any]:
        """Provide sample user data for testing."""
        return {
            "id": str(uuid4()),
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$LJ3m4ys3Lk5jH6k7J8l9M0n1O2p3Q4r5S6t7U8v9W0x1y2z3A4B5C6D7E8F9",
            "full_name": "Test User",
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

    @pytest.fixture
    def sample_user_create(self) -> UserCreate:
        """Provide a sample user creation schema."""
        return UserCreate(
            email="newuser@example.com",
            username="newuser",
            password="SecurePass123!",
            full_name="New User",
        )

    @pytest.fixture
    def sample_user_update(self) -> UserUpdate:
        """Provide a sample user update schema."""
        return UserUpdate(
            full_name="Updated Name",
            is_active=False,
        )

    @pytest.mark.asyncio
    async def test_create_user_success(
        self,
        mock_user_repository: Mock,
        sample_user_create: UserCreate,
    ) -> None:
        """Test successful user creation."""
        # Arrange
        expected_user = User(
            id=str(uuid4()),
            email=sample_user_create.email,
            username=sample_user_create.username,
            full_name=sample_user_create.full_name,
            is_active=True,
            is_verified=False,
        )
        mock_user_repository.create.return_value = expected_user

        # Act
        result = await create_user(
            user_data=sample_user_create,
            repository=mock_user_repository,
        )

        # Assert
        assert isinstance(result, UserResponse)
        assert result.email == sample_user_create.email
        assert result.username == sample_user_create.username
        assert result.full_name == sample_user_create.full_name
        assert result.is_active is True
        assert result.is_verified is False
        mock_user_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(
        self,
        mock_user_repository: Mock,
        sample_user_create: UserCreate,
    ) -> None:
        """Test user creation with duplicate email."""
        # Arrange
        mock_user_repository.create.side_effect = DuplicateResourceError(
            "User with this email already exists"
        )

        # Act & Assert
        with pytest.raises(DuplicateResourceError) as exc_info:
            await create_user(
                user_data=sample_user_create,
                repository=mock_user_repository,
            )
        assert "email" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_user_invalid_data(
        self,
        mock_user_repository: Mock,
    ) -> None:
        """Test user creation with invalid data."""
        # Arrange
        invalid_data = UserCreate(
            email="invalid-email",
            username="",
            password="weak",
            full_name="",
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await create_user(
                user_data=invalid_data,
                repository=mock_user_repository,
            )
        assert "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_user_success(
        self,
        mock_user_repository: Mock,
        sample_user_data: Dict[str, Any],
    ) -> None:
        """Test successful user retrieval."""
        # Arrange
        user_id = sample_user_data["id"]
        expected_user = User(**sample_user_data)
        mock_user_repository.get_by_id.return_value = expected_user

        # Act
        result = await get_user(
            user_id=user_id,
            repository=mock_user_repository,
        )

        # Assert
        assert isinstance(result, UserResponse)
        assert result.id == user_id
        assert result.email == sample_user_data["email"]
        mock_user_repository.get_by_id.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_not_found(
        self,
        mock_user_repository: Mock,
    ) -> None:
        """Test user retrieval with non-existent ID."""
        # Arrange
        user_id = str(uuid4())
        mock_user_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await get_user(
                user_id=user_id,
                repository=mock_user_repository,
            )
        assert "user" in str(exc_info.value).lower()
        assert user_id in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_success(
        self,
        mock_user_repository: Mock,
        sample_user_data: Dict[str, Any],
        sample_user_update: UserUpdate,
    ) -> None:
        """Test successful user update."""
        # Arrange
        user_id = sample_user_data["id"]
        existing_user = User(**sample_user_data)
        updated_user = User(
            **{**sample_user_data, **sample_user_update.dict(exclude_unset=True)}
        )
        mock_user_repository.get_by_id.return_value = existing_user
        mock_user_repository.update.return_value = updated_user

        # Act
        result = await update_user(
            user_id=user_id,
            update_data=sample_user_update,
            repository=mock_user_repository,
        )

        # Assert
        assert isinstance(result, UserResponse)
        assert result.full_name == sample_user_update.full_name
        assert result.is_active == sample_user_update.is_active
        mock_user_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(
        self,
        mock_user_repository: Mock,
        sample_user_update: UserUpdate,
    ) -> None:
        """Test user update with non-existent ID."""
        # Arrange
        user_id = str(uuid4())
        mock_user_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await update_user(
                user_id=user_id,
                update_data=sample_user_update,
                repository=mock_user_repository,
            )
        assert "user" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_delete_user_success(
        self,
        mock_user_repository: Mock,
        sample_user_data: Dict[str, Any],
    ) -> None:
        """Test successful user deletion."""
        # Arrange
        user_id = sample_user_data["id"]
        existing_user = User(**sample_user_data)
        mock_user_repository.get_by_id.return_value = existing_user
        mock_user_repository.delete.return_value = True

        # Act
        result = await delete_user(
            user_id=user_id,
            repository=mock_user_repository,
        )

        # Assert
        assert result is True
        mock_user_repository.delete.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_delete_user_not_found(
        self,
        mock_user_repository: Mock,
    ) -> None:
        """Test user deletion with non-existent ID."""
        # Arrange
        user_id = str(uuid4())
        mock_user_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await delete_user(
                user_id=user_id,
                repository=mock_user_repository,
            )
        assert "user" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_list_users_success(
        self,
        mock_user_repository: Mock,
        sample_user_data: Dict[str, Any],
    ) -> None:
        """Test successful user listing."""
        # Arrange
        users = [User(**sample_user_data) for _ in range(3)]
        mock_user_repository.list_all.return_value = users

        # Act
        result = await list_users(
            repository=mock_user_repository,
            skip=0,
            limit=10,
        )

        # Assert
        assert len(result) == 3
        assert all(isinstance(user, UserResponse) for user in result)
        mock_user_repository.list_all.assert_called_once_with(skip=0, limit=10)

    @pytest.mark.asyncio
    async def test_list_users_empty(
        self,
        mock_user_repository: Mock,
    ) -> None:
        """Test user listing with no users."""
        # Arrange
        mock_user_repository.list_all.return_value = []

        # Act
        result = await list_users(
            repository=mock_user_repository,
            skip=0,
            limit=10,
        )

        # Assert
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
        self,
        mock_user_repository: Mock,
        sample_user_data: Dict[str, Any],
    ) -> None:
        """Test successful user authentication."""
        # Arrange
        email = sample_user_data["email"]
        password = "correct_password"
        user = User(**sample_user_data)
        mock_user_repository.get_by_email.return_value = user

        with patch("app.services.verify_password") as mock_verify:
            mock_verify.return_value = True

            # Act
            result = await authenticate_user(
                email=email,
                password=password,
                repository=mock_user_repository,
            )

            # Assert
            assert isinstance(result, UserResponse)
            assert result.email == email
            mock_verify.assert_called_once_with(password, user.password_hash)

    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_credentials(
        self,
        mock_user_repository: Mock,
    ) -> None:
        """Test authentication with invalid credentials."""
        # Arrange
        email = "nonexistent@example.com"
        password = "wrong_password"
        mock_user_repository.get_by_email.return_value = None

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            await authenticate_user(
                email=email,
                password=password,
                repository=mock_user_repository,
            )
        assert "invalid" in str(exc_info.value).lower()


class TestTokenService:
    """Test suite for token-related service functions."""

    @pytest.fixture
    def mock_token_repository(self) -> Mock:
        """Create a mock token repository."""
        return Mock()

    @pytest.fixture
    def sample_token_data(self) -> Dict[str, Any]:
        """Provide sample token data for testing."""
        return {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4...",
            "expires_at": datetime.utcnow() + timedelta(hours=1),
            "is_revoked": False,
            "created_at": datetime.utcnow(),
        }

    @pytest.mark.asyncio
    async def test_generate_token_success(
        self,
        mock_token_repository: Mock,
        sample_token_data: Dict[str, Any],
    ) -> None:
        """Test successful token generation."""
        # Arrange
        user_id = sample_token_data["user_id"]
        expected_token = Token(**sample_token_data)
        mock_token_repository.create.return_value = expected_token

        with patch("app.services.create_access_token") as mock_create_access:
            mock_create_access.return_value = sample_token_data["access_token"]
            with patch("app.services.create_refresh_token") as mock_create_refresh:
                mock_create_refresh.return_value = sample_token_data["refresh_token"]

                # Act
                result = await generate_token(
                    user_id=user_id,
                    token_repository=mock_token_repository,
                )

                # Assert
                assert isinstance(result, TokenResponse)
                assert result.access_token == sample_token_data["access_token"]
                assert result.refresh_token == sample_token_data["refresh_token"]
                mock_token_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_token_failure(
        self,
        mock_token_repository: Mock,
    ) -> None:
        """Test token generation failure."""
        # Arrange
        user_id = str(uuid4())
        mock_token_repository.create.side_effect = ServiceError(
            "Failed to generate token"
        )

        # Act & Assert
        with pytest.raises(ServiceError) as exc_info:
            await generate_token(
                user_id=user_id,
                token_repository=mock_token_repository,
            )
        assert "token" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_token_success(
        self,
        mock_token_repository: Mock,
        sample_token_data: Dict[str, Any],
    ) -> None:
        """Test successful token validation."""
        # Arrange
        access_token = sample_token_data["access_token"]
        expected_token = Token(**sample_token_data)
        mock_token_repository.get_by_access_token.return_value = expected_token

        with patch("app.services.decode_token") as mock_decode:
            mock_decode.return_value = {"user_id": sample_token_data["user_id"]}

            # Act
            result = await validate_token(
                token=access_token,
                token_repository=mock_token_repository,
            )

            # Assert
            assert isinstance(result, TokenResponse)
            assert result.access_token == access_token
            assert result.is_revoked is False

    @pytest.mark.asyncio
    async def test_validate_token_expired(
        self,
        mock_token_repository: Mock,
        sample_token_data: Dict[str, Any],
    ) -> None:
        """Test validation of expired token."""
        # Arrange
        expired_token_data = {**sample_token_data, "expires_at": datetime.utcnow() - timedelta(hours=1)}
        access_token = expired_token_data["access_token"]
        expired_token = Token(**expired_token_data)
        mock_token_repository.get_by_access_token.return_value = expired_token

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            await validate_token(
                token=access_token,
                token_repository=mock_token_repository,
            )
        assert "expired" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_token_revoked(
        self,
        mock_token_repository: Mock,
        sample_token_data: Dict[str, Any],
    ) -> None:
        """Test validation of revoked token."""
        # Arrange
        revoked_token_data = {**sample_token_data, "is_revoked": True}
        access_token = revoked_token_data["access_token"]
        revoked_token = Token(**revoked_token_data)
        mock_token_repository.get_by_access_token.return_value = revoked_token

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            await validate_token(
                token=access_token,
                token_repository=mock_token_repository,
            )
        assert "revoked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_revoke_token_success(
        self,
        mock_token_repository: Mock,
        sample_token_data: Dict[str, Any],
    ) -> None:
        """Test successful token revocation."""
        # Arrange
        token_id = sample_token_data["id"]
        existing_token = Token(**sample_token_data)
        mock_token_repository.get_by_id.return_value = existing_token
        mock_token_repository.revoke.return_value = True

        # Act
        result = await revoke_token(
            token_id=token_id,
            token_repository=mock_token_repository,
        )

        # Assert
        assert result is True
        mock_token_repository.revoke.assert_called_once_with(token_id)

    @pytest.mark.asyncio
    async def test_revoke_token_not_found(
        self,
        mock_token_repository: Mock,
    ) -> None:
        """Test token revocation with non-existent ID."""
        # Arrange
        token_id = str(uuid4())
        mock_token_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await revoke_token(
                token_id=token_id,
                token_repository=mock_token_repository,
            )
        assert "token" in str(exc_info.value).lower()


class TestNotificationService:
    """Test suite for notification-related service functions."""

    @pytest.fixture
    def mock_notification_repository(self) -> Mock:
        """Create a mock notification repository."""
        return Mock()

    @pytest.fixture
    def mock_email_service(self) -> Mock:
        """Create a mock email service."""
        return Mock()

    @pytest.fixture
    def sample_notification_request(self) -> NotificationRequest:
        """Provide a sample notification request."""
        return NotificationRequest(
            user_id=str(uuid4()),
            notification_type="email",
            subject="Test Notification",
            body="This is a test notification.",
            priority="high",
        )

    @pytest.mark.asyncio
    async def test_send_notification_success(
        self,
        mock_notification_repository: Mock,
        mock_email_service: Mock,
        sample_notification_request: NotificationRequest,
    ) -> None:
        """Test successful notification sending."""
        # Arrange
        expected_notification = Notification(
            id=str(uuid4()),
            user_id=sample_notification_request.user_id,
            notification_type=sample_notification_request.notification_type,
            subject=sample_notification_request.subject,
            body=sample_notification_request.body,
            priority=sample_notification_request.priority,
            status="sent",
            sent_at=datetime.utcnow(),
        )
        mock_notification_repository.create.return_value = expected_notification
        mock_email_service.send.return_value = True

        # Act
        result = await send_notification(
            notification_request=sample_notification_request,
            notification_repository=mock_notification_repository,
            email_service=mock_email_service,
        )

        # Assert
        assert isinstance(result, Notification)
        assert result.status == "sent"
        assert result.subject == sample_notification_request.subject
        mock_email_service.send.assert_called_once()
        mock_notification_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_email_failure(
        self,
        mock_notification_repository: Mock,
        mock_email_service: Mock,
        sample_notification_request: NotificationRequest,
    ) -> None:
        """Test notification sending with email service failure."""
        # Arrange
        mock_email_service.send.side_effect = NotificationError(
            "Failed to send email"
        )

        # Act & Assert
        with pytest.raises(NotificationError) as exc_info:
            await send_notification(
                notification_request=sample_notification_request,
                notification_repository=mock_notification_repository,
                email_service=mock_email_service,
            )
        assert "email" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_send_notification_invalid_type(
        self,
        mock_notification_repository: Mock,
        mock_email_service: Mock,
    ) -> None:
        """Test notification sending with invalid type."""
        # Arrange
        invalid_request = NotificationRequest(
            user_id=str(uuid4()),
            notification_type="invalid_type",
            subject="Test",
            body="Test body",
            priority="low",
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await send_notification(
                notification_request=invalid_request,
                notification_repository=mock_notification_repository,
                email_service=mock_email_service,
            )
        assert "notification type" in str(exc_info.value).lower()


class TestPaymentService:
    """Test suite for payment-related service functions."""

    @pytest.fixture
    def mock_payment_repository(self) -> Mock:
        """Create a mock payment repository."""
        return Mock()

    @pytest.fixture
    def mock_payment_gateway(self) -> Mock:
        """Create a mock payment gateway."""
        return Mock()

    @pytest.fixture
    def sample_payment_request(self) -> PaymentRequest:
        """Provide a sample payment request."""
        return PaymentRequest(
            user_id=str(uuid4()),
            amount=100.00,
            currency="USD",
            payment_method="credit_card",
            description="Test payment",
        )

    @pytest.mark.asyncio
    async def test_process_payment_success(
        self,
        mock_payment_repository: Mock,
        mock_payment_gateway: Mock,
        sample_payment_request: PaymentRequest,
    ) -> None:
        """Test successful payment processing."""
        # Arrange
        expected_payment = Payment(
            id=str(uuid4()),
            user_id=sample_payment_request.user_id,
            amount=sample_payment_request.amount,
            currency=sample_payment_request.currency,
            payment_method=sample_payment_request.payment_method,
            description=sample_payment_request.description,
            status="completed",
            transaction_id="txn_1234567890",
            processed_at=datetime.utcnow(),
        )
        mock_payment_gateway.charge.return_value = {
            "success": True,
            "transaction_id": "txn_1234567890",
        }
        mock_payment_repository.create.return_value = expected_payment

        # Act
        result = await process_payment(
            payment_request=sample_payment_request,
            payment_repository=mock_payment_repository,
            payment_gateway=mock_payment_gateway,
        )

        # Assert
        assert isinstance(result, Payment)
        assert result.status == "completed"
        assert result.transaction_id == "txn_1234567890"
        assert result.amount == sample_payment_request.amount
        mock_payment_gateway.charge.assert_called_once()
        mock_payment_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_payment_declined(
        self,
        mock_payment_repository: Mock,
        mock_payment_gateway: Mock,
        sample_payment_request: PaymentRequest,
    ) -> None:
        """Test payment processing with declined transaction."""
        # Arrange
        mock_payment_gateway.charge.return_value = {
            "success": False,
            "error": "Card declined",
        }

        # Act & Assert
        with pytest.raises(PaymentError) as exc_info:
            await process_payment(
                payment_request=sample_payment_request,
                payment_repository=mock_payment_repository,
                payment_gateway=mock_payment_gateway,
            )
        assert "declined" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_process_payment_invalid_amount(
        self,
        mock_payment_repository: Mock,
        mock_payment_gateway: Mock,
    ) -> None:
        """Test payment processing with invalid amount."""
        # Arrange
        invalid_request = PaymentRequest(
            user_id=str(uuid4()),
            amount=-50.00,
            currency="USD",
            payment_method="credit_card",
            description="Invalid payment",
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await process_payment(
                payment_request=invalid_request,
                payment_repository=mock_payment_repository,
                payment_gateway=mock_payment_gateway,
            )
        assert "amount" in str(exc_info.value).lower()


class TestMetricsService:
    """Test suite for metrics-related service functions."""

    @pytest.fixture
    def mock_metrics_repository(self) -> Mock:
        """Create a mock metrics repository."""
        return Mock()

    @pytest.mark.asyncio
    async def test_calculate_metrics_success(
        self,
        mock_metrics_repository: Mock,
    ) -> None:
        """Test successful metrics calculation."""
        # Arrange
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        expected_metrics = {
            "total_users": 1000,
            "active_users": 750,
            "total_revenue": 50000.00,
            "average_order_value": 50.00,
            "conversion_rate": 0.05,
            "churn_rate": 0.02,
        }
        mock_metrics_repository.calculate.return_value = expected_metrics

        # Act
        result = await calculate_metrics(
            start_date=start_date,
            end_date=end_date,
            metrics_repository=mock_metrics_repository,
        )

        # Assert
        assert isinstance(result, MetricsResponse)
        assert result.total_users == 1000
        assert result.active_users == 750
        assert result.total_revenue == 50000.00
        assert result.average_order_value == 50.00
        assert result.conversion_rate == 0.05
        assert result.churn_rate == 0.02
        mock_metrics_repository.calculate.assert_called_once_with(
            start_date=start_date,
            end_date=end_date,
        )

    @pytest.mark.asyncio
    async def test_calculate_metrics_invalid_date_range(
        self,
        mock_metrics_repository: Mock,
    ) -> None:
        """Test metrics calculation with invalid date range."""
        # Arrange
        start_date = datetime.utcnow()
        end_date = datetime.utcnow() - timedelta(days=30)  # End before start

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await calculate_metrics(
                start_date=start_date,
                end_date=end_date,
                metrics_repository=mock_metrics_repository,
            )
        assert "date range" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_calculate_metrics_no_data(
        self,
        mock_metrics_repository: Mock,
    ) -> None:
        """Test metrics calculation with no data available."""
        # Arrange
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        mock_metrics_repository.calculate.return_value = {
            "total_users": 0,
            "active_users": 0,
            "total_revenue": 0.0,
            "average_order_value": 0.0,
            "conversion_rate": 0.0,
            "churn_rate": 0.0,
        }

        # Act
        result = await calculate_metrics(
            start_date=start_date,
            end_date=end_date,
            metrics_repository=mock_metrics_repository,
        )

        # Assert
        assert isinstance(result, MetricsResponse)
        assert result.total_users == 0
        assert result.total_revenue == 0.0


class TestServiceErrorHandling:
    """Test suite for general service error handling."""

    @pytest.mark.asyncio
    async def test_service_unavailable(self) -> None:
        """Test handling of service unavailability."""
        # Arrange
        mock_repository = Mock()
        mock_repository.create.side_effect = ConnectionError("Database connection failed")

        # Act & Assert
        with pytest.raises(ServiceError) as exc_info:
            await create_user(
                user_data=UserCreate(
                    email="test@example.com",
                    username="test",
                    password="Test123!",
                    full_name="Test",
                ),
                repository=mock_repository,
            )
        assert "service" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test handling of timeout errors."""
        # Arrange
        mock_repository = Mock()
        mock_repository.get_by_id.side_effect = TimeoutError("Operation timed out")

        # Act & Assert
        with pytest.raises(ServiceError) as exc_info:
            await get_user(
                user_id=str(uuid4()),
                repository=mock_repository,
            )
        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_rate_limiting(self) -> None:
        """Test handling of rate limiting."""
        # Arrange
        mock_repository = Mock()
        mock_repository.list_all.side_effect = Exception("Rate limit exceeded")

        # Act & Assert
        with pytest.raises(ServiceError) as exc_info:
            await list_users(
                repository=mock_repository,
                skip=0,
                limit=10,
            )
        assert "rate" in str(exc_info.value).lower()