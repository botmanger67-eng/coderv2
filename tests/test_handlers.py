"""
Unit tests for request handlers.

This module contains comprehensive tests for all request handler functions,
including success cases, error cases, and edge cases.
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from src.handlers import (
    handle_create_item,
    handle_get_item,
    handle_update_item,
    handle_delete_item,
    handle_list_items,
    handle_batch_operation,
    handle_health_check,
    handle_error,
    RequestContext,
    HandlerResponse,
    HandlerError,
    ValidationError,
    NotFoundError,
    ConflictError,
)


@pytest.fixture
def mock_request_context() -> RequestContext:
    """Create a mock request context for testing."""
    return RequestContext(
        request_id="test-request-123",
        user_id="test-user-456",
        timestamp=datetime.now(timezone.utc),
        source_ip="127.0.0.1",
        user_agent="pytest/1.0",
    )


@pytest.fixture
def valid_item_data() -> Dict[str, Any]:
    """Create valid item data for testing."""
    return {
        "name": "test-item",
        "description": "A test item for unit testing",
        "price": 29.99,
        "category": "electronics",
        "tags": ["test", "sample"],
        "metadata": {
            "color": "black",
            "weight": 1.5,
        },
    }


@pytest.fixture
def mock_item_service() -> Mock:
    """Create a mock item service."""
    service = Mock()
    service.create_item = AsyncMock()
    service.get_item = AsyncMock()
    service.update_item = AsyncMock()
    service.delete_item = AsyncMock()
    service.list_items = AsyncMock()
    service.batch_operation = AsyncMock()
    return service


class TestHandleCreateItem:
    """Tests for the handle_create_item function."""

    @pytest.mark.asyncio
    async def test_successful_creation(
        self,
        mock_request_context: RequestContext,
        valid_item_data: Dict[str, Any],
        mock_item_service: Mock,
    ) -> None:
        """Test successful item creation."""
        expected_item = {
            "id": "item-789",
            **valid_item_data,
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
        }
        mock_item_service.create_item.return_value = expected_item

        response: HandlerResponse = await handle_create_item(
            request_context=mock_request_context,
            item_data=valid_item_data,
            item_service=mock_item_service,
        )

        assert response.status_code == 201
        assert response.body["success"] is True
        assert response.body["data"] == expected_item
        assert response.body["request_id"] == mock_request_context.request_id
        mock_item_service.create_item.assert_awaited_once_with(
            item_data=valid_item_data,
            user_id=mock_request_context.user_id,
        )

    @pytest.mark.asyncio
    async def test_validation_error(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test creation with invalid data."""
        invalid_data: Dict[str, Any] = {
            "name": "",  # Empty name should fail validation
            "price": -10.0,  # Negative price should fail validation
        }
        mock_item_service.create_item.side_effect = ValidationError(
            message="Invalid item data",
            errors={
                "name": "Name cannot be empty",
                "price": "Price must be positive",
            },
        )

        response: HandlerResponse = await handle_create_item(
            request_context=mock_request_context,
            item_data=invalid_data,
            item_service=mock_item_service,
        )

        assert response.status_code == 400
        assert response.body["success"] is False
        assert "errors" in response.body
        assert response.body["error_type"] == "ValidationError"

    @pytest.mark.asyncio
    async def test_conflict_error(
        self,
        mock_request_context: RequestContext,
        valid_item_data: Dict[str, Any],
        mock_item_service: Mock,
    ) -> None:
        """Test creation when item already exists."""
        mock_item_service.create_item.side_effect = ConflictError(
            message="Item with this name already exists",
            item_id="existing-item-123",
        )

        response: HandlerResponse = await handle_create_item(
            request_context=mock_request_context,
            item_data=valid_item_data,
            item_service=mock_item_service,
        )

        assert response.status_code == 409
        assert response.body["success"] is False
        assert response.body["error_type"] == "ConflictError"

    @pytest.mark.asyncio
    async def test_unexpected_error(
        self,
        mock_request_context: RequestContext,
        valid_item_data: Dict[str, Any],
        mock_item_service: Mock,
    ) -> None:
        """Test creation with unexpected service error."""
        mock_item_service.create_item.side_effect = Exception("Database connection failed")

        response: HandlerResponse = await handle_create_item(
            request_context=mock_request_context,
            item_data=valid_item_data,
            item_service=mock_item_service,
        )

        assert response.status_code == 500
        assert response.body["success"] is False
        assert response.body["error_type"] == "InternalServerError"


class TestHandleGetItem:
    """Tests for the handle_get_item function."""

    @pytest.mark.asyncio
    async def test_successful_retrieval(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test successful item retrieval."""
        item_id = "item-789"
        expected_item = {
            "id": item_id,
            "name": "test-item",
            "description": "A test item",
            "price": 29.99,
        }
        mock_item_service.get_item.return_value = expected_item

        response: HandlerResponse = await handle_get_item(
            request_context=mock_request_context,
            item_id=item_id,
            item_service=mock_item_service,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.body["data"] == expected_item
        mock_item_service.get_item.assert_awaited_once_with(
            item_id=item_id,
            user_id=mock_request_context.user_id,
        )

    @pytest.mark.asyncio
    async def test_item_not_found(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test retrieval of non-existent item."""
        item_id = "non-existent-item"
        mock_item_service.get_item.side_effect = NotFoundError(
            message=f"Item {item_id} not found",
            item_id=item_id,
        )

        response: HandlerResponse = await handle_get_item(
            request_context=mock_request_context,
            item_id=item_id,
            item_service=mock_item_service,
        )

        assert response.status_code == 404
        assert response.body["success"] is False
        assert response.body["error_type"] == "NotFoundError"

    @pytest.mark.asyncio
    async def test_invalid_item_id(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test retrieval with invalid item ID format."""
        invalid_id = ""
        mock_item_service.get_item.side_effect = ValidationError(
            message="Invalid item ID format",
            errors={"item_id": "Item ID cannot be empty"},
        )

        response: HandlerResponse = await handle_get_item(
            request_context=mock_request_context,
            item_id=invalid_id,
            item_service=mock_item_service,
        )

        assert response.status_code == 400
        assert response.body["success"] is False


class TestHandleUpdateItem:
    """Tests for the handle_update_item function."""

    @pytest.mark.asyncio
    async def test_successful_update(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test successful item update."""
        item_id = "item-789"
        update_data = {
            "name": "updated-item",
            "price": 39.99,
        }
        expected_item = {
            "id": item_id,
            **update_data,
            "description": "A test item",
            "updated_at": "2024-01-15T11:00:00Z",
        }
        mock_item_service.update_item.return_value = expected_item

        response: HandlerResponse = await handle_update_item(
            request_context=mock_request_context,
            item_id=item_id,
            update_data=update_data,
            item_service=mock_item_service,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.body["data"] == expected_item
        mock_item_service.update_item.assert_awaited_once_with(
            item_id=item_id,
            update_data=update_data,
            user_id=mock_request_context.user_id,
        )

    @pytest.mark.asyncio
    async def test_update_not_found(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test update of non-existent item."""
        item_id = "non-existent-item"
        update_data = {"name": "updated-name"}
        mock_item_service.update_item.side_effect = NotFoundError(
            message=f"Item {item_id} not found",
            item_id=item_id,
        )

        response: HandlerResponse = await handle_update_item(
            request_context=mock_request_context,
            item_id=item_id,
            update_data=update_data,
            item_service=mock_item_service,
        )

        assert response.status_code == 404
        assert response.body["success"] is False


class TestHandleDeleteItem:
    """Tests for the handle_delete_item function."""

    @pytest.mark.asyncio
    async def test_successful_deletion(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test successful item deletion."""
        item_id = "item-789"
        mock_item_service.delete_item.return_value = True

        response: HandlerResponse = await handle_delete_item(
            request_context=mock_request_context,
            item_id=item_id,
            item_service=mock_item_service,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.body["message"] == f"Item {item_id} deleted successfully"
        mock_item_service.delete_item.assert_awaited_once_with(
            item_id=item_id,
            user_id=mock_request_context.user_id,
        )

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test deletion of non-existent item."""
        item_id = "non-existent-item"
        mock_item_service.delete_item.side_effect = NotFoundError(
            message=f"Item {item_id} not found",
            item_id=item_id,
        )

        response: HandlerResponse = await handle_delete_item(
            request_context=mock_request_context,
            item_id=item_id,
            item_service=mock_item_service,
        )

        assert response.status_code == 404
        assert response.body["success"] is False


class TestHandleListItems:
    """Tests for the handle_list_items function."""

    @pytest.mark.asyncio
    async def test_successful_listing(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test successful item listing."""
        filters = {"category": "electronics", "page": 1, "per_page": 10}
        expected_items = [
            {"id": "item-1", "name": "Item 1", "category": "electronics"},
            {"id": "item-2", "name": "Item 2", "category": "electronics"},
        ]
        expected_total = 2
        mock_item_service.list_items.return_value = (expected_items, expected_total)

        response: HandlerResponse = await handle_list_items(
            request_context=mock_request_context,
            filters=filters,
            item_service=mock_item_service,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.body["data"]["items"] == expected_items
        assert response.body["data"]["total"] == expected_total
        assert response.body["data"]["page"] == 1
        assert response.body["data"]["per_page"] == 10
        mock_item_service.list_items.assert_awaited_once_with(
            filters=filters,
            user_id=mock_request_context.user_id,
        )

    @pytest.mark.asyncio
    async def test_empty_listing(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test listing with no results."""
        filters = {"category": "nonexistent"}
        mock_item_service.list_items.return_value = ([], 0)

        response: HandlerResponse = await handle_list_items(
            request_context=mock_request_context,
            filters=filters,
            item_service=mock_item_service,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.body["data"]["items"] == []
        assert response.body["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_invalid_filters(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test listing with invalid filters."""
        invalid_filters = {"page": -1, "per_page": 0}
        mock_item_service.list_items.side_effect = ValidationError(
            message="Invalid filter parameters",
            errors={
                "page": "Page must be positive",
                "per_page": "Per page must be positive",
            },
        )

        response: HandlerResponse = await handle_list_items(
            request_context=mock_request_context,
            filters=invalid_filters,
            item_service=mock_item_service,
        )

        assert response.status_code == 400
        assert response.body["success"] is False


class TestHandleBatchOperation:
    """Tests for the handle_batch_operation function."""

    @pytest.mark.asyncio
    async def test_successful_batch_operation(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test successful batch operation."""
        batch_request = {
            "operations": [
                {"type": "create", "data": {"name": "Item 1", "price": 10.0}},
                {"type": "update", "item_id": "item-2", "data": {"price": 20.0}},
                {"type": "delete", "item_id": "item-3"},
            ]
        }
        expected_results = {
            "successful": [
                {"operation": "create", "item_id": "new-item-1"},
                {"operation": "update", "item_id": "item-2"},
                {"operation": "delete", "item_id": "item-3"},
            ],
            "failed": [],
        }
        mock_item_service.batch_operation.return_value = expected_results

        response: HandlerResponse = await handle_batch_operation(
            request_context=mock_request_context,
            batch_request=batch_request,
            item_service=mock_item_service,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.body["data"] == expected_results
        mock_item_service.batch_operation.assert_awaited_once_with(
            operations=batch_request["operations"],
            user_id=mock_request_context.user_id,
        )

    @pytest.mark.asyncio
    async def test_batch_with_partial_failures(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test batch operation with some failures."""
        batch_request = {
            "operations": [
                {"type": "create", "data": {"name": "Item 1"}},
                {"type": "update", "item_id": "invalid-id", "data": {"price": 20.0}},
            ]
        }
        expected_results = {
            "successful": [
                {"operation": "create", "item_id": "new-item-1"},
            ],
            "failed": [
                {
                    "operation": "update",
                    "item_id": "invalid-id",
                    "error": "Item not found",
                },
            ],
        }
        mock_item_service.batch_operation.return_value = expected_results

        response: HandlerResponse = await handle_batch_operation(
            request_context=mock_request_context,
            batch_request=batch_request,
            item_service=mock_item_service,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert len(response.body["data"]["successful"]) == 1
        assert len(response.body["data"]["failed"]) == 1

    @pytest.mark.asyncio
    async def test_batch_validation_error(
        self,
        mock_request_context: RequestContext,
        mock_item_service: Mock,
    ) -> None:
        """Test batch operation with invalid request format."""
        invalid_batch_request = {"operations": "not-a-list"}
        mock_item_service.batch_operation.side_effect = ValidationError(
            message="Invalid batch request format",
            errors={"operations": "Operations must be a list"},
        )

        response: HandlerResponse = await handle_batch_operation(
            request_context=mock_request_context,
            batch_request=invalid_batch_request,
            item_service=mock_item_service,
        )

        assert response.status_code == 400
        assert response.body["success"] is False


class TestHandleHealthCheck:
    """Tests for the handle_health_check function."""

    @pytest.mark.asyncio
    async def test_healthy_service(
        self,
        mock_request_context: RequestContext,
    ) -> None:
        """Test health check when service is healthy."""
        response: HandlerResponse = await handle_health_check(
            request_context=mock_request_context,
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.body["status"] == "healthy"
        assert "timestamp" in response.body
        assert response.body["request_id"] == mock_request_context.request_id

    @pytest.mark.asyncio
    async def test_health_check_response_structure(
        self,
        mock_request_context: RequestContext,
    ) -> None:
        """Test health check response contains all required fields."""
        response: HandlerResponse = await handle_health_check(
            request_context=mock_request_context,
        )

        required_fields = ["success", "status", "timestamp", "request_id", "version"]
        for field in required_fields:
            assert field in response.body, f"Missing required field: {field}"


class TestHandleError:
    """Tests for the handle_error function."""

    def test_handler_error_response(self) -> None:
        """Test error response generation for HandlerError."""
        error = HandlerError(
            message="Custom handler error",
            status_code=400,
            error_code="HANDLER_ERROR",
            details={"field": "value"},
        )

        response: HandlerResponse = handle_error(error)

        assert response.status_code == 400
        assert response.body["success"] is False
        assert response.body["error"] == "Custom handler error"
        assert response.body["error_code"] == "HANDLER_ERROR"
        assert response.body["details"] == {"field": "value"}

    def test_validation_error_response(self) -> None:
        """Test error response generation for ValidationError."""
        error = ValidationError(
            message="Validation failed",
            errors={"name": "Name is required"},
        )

        response: HandlerResponse = handle_error(error)

        assert response.status_code == 400
        assert response.body["success"] is False
        assert response.body["error_type"] == "ValidationError"
        assert response.body["errors"] == {"name": "Name is required"}

    def test_not_found_error_response(self) -> None:
        """Test error response generation for NotFoundError."""
        error = NotFoundError(
            message="Resource not found",
            item_id="item-123",
        )

        response: HandlerResponse = handle_error(error)

        assert response.status_code == 404
        assert response.body["success"] is False
        assert response.body["error_type"] == "NotFoundError"
        assert response.body["item_id"] == "item-123"

    def test_conflict_error_response(self) -> None:
        """Test error response generation for ConflictError."""
        error = ConflictError(
            message="Resource conflict",
            item_id="item-123",
        )

        response: HandlerResponse = handle_error(error)

        assert response.status_code == 409
        assert response.body["success"] is False
        assert response.body["error_type"] == "ConflictError"

    def test_generic_exception_response(self) -> None:
        """Test error response generation for generic exceptions."""
        error = Exception("Unexpected error occurred")

        response: HandlerResponse = handle_error(error)

        assert response.status_code == 500
        assert response.body["success"] is False
        assert response.body["error_type"] == "InternalServerError"
        assert "Unexpected error occurred" in response.body["error"]

    def test_error_response_with_request_id(self) -> None:
        """Test error response includes request ID when available."""
        error = HandlerError(
            message="Error with context",
            status_code=500,
            request_id="req-123",
        )

        response: HandlerResponse = handle_error(error)

        assert response.body["request_id"] == "req-123"


class TestHandlerResponse:
    """Tests for the HandlerResponse class."""

    def test_response_creation(self) -> None:
        """Test HandlerResponse creation with valid data."""
        response = HandlerResponse(
            status_code=200,
            body={"success": True, "data": {"key": "value"}},
            headers={"X-Custom-Header": "value"},
        )

        assert response.status_code == 200
        assert response.body["success"] is True
        assert response.headers["X-Custom-Header"] == "value"

    def test_response_default_headers(self) -> None:
        """Test HandlerResponse includes default headers."""
        response = HandlerResponse(
            status_code=200,
            body={"success": True},
        )

        assert "Content-Type" in response.headers
        assert response.headers["Content-Type"] == "application/json"

    def test_response_serialization(self) -> None:
        """Test HandlerResponse can be serialized to JSON."""
        response = HandlerResponse(
            status_code=200,
            body={"success": True, "data": {"name": "test"}},
        )

        json_str = json.dumps(response.body)
        parsed = json.loads(json_str)
        assert parsed["success"] is True
        assert parsed["data"]["name"] == "test"


class TestRequestContext:
    """Tests for the RequestContext class."""

    def test_context_creation(self) -> None:
        """Test RequestContext creation with valid data."""
        context = RequestContext(
            request_id="req-123",
            user_id="user-456",
            timestamp=datetime.now(timezone.utc),
            source_ip="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert context.request_id == "req-123"
        assert context.user_id == "user-456"
        assert context.source_ip == "192.168.1.1"

    def test_context_default_values(self) -> None:
        """Test RequestContext with optional fields."""
        context = RequestContext(
            request_id="req-123",
            user_id="user-456",
            timestamp=datetime.now(timezone.utc),
        )

        assert context.source_ip is None
        assert context.user_agent is None

    def test_context_to_dict(self) -> None:
        """Test RequestContext conversion to dictionary."""
        context = RequestContext(
            request_id="req-123",
            user_id="user-456",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            source_ip="192.168.1.1",
        )

        context_dict = context.to_dict()
        assert context_dict["request_id"] == "req-123"
        assert context_dict["user_id"] == "user-456"
        assert context_dict["source_ip"] == "192.168.1.1"
        assert "timestamp" in context_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])