# API Documentation

## Overview

This document provides comprehensive documentation for the Enterprise API. The API follows RESTful principles and uses JSON for request/response payloads.

## Base URL

```
https://api.example.com/v1
```

## Authentication

All API requests require authentication via Bearer token.

```http
Authorization: Bearer <your-api-token>
```

## Endpoints

### Health Check

#### GET /health

Returns the current health status of the API.

**Response**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0"
}
```

### Users

#### POST /users

Creates a new user.

**Request Body**

```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "role": "admin"
}
```

**Response**

```json
{
  "id": "usr_1234567890",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "admin",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `400 Bad Request`: Invalid input data
- `409 Conflict`: Email already exists

#### GET /users/{user_id}

Retrieves a user by ID.

**Parameters**

- `user_id` (string, required): The unique identifier of the user

**Response**

```json
{
  "id": "usr_1234567890",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "admin",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `404 Not Found`: User not found

#### PUT /users/{user_id}

Updates an existing user.

**Parameters**

- `user_id` (string, required): The unique identifier of the user

**Request Body**

```json
{
  "name": "Jane Doe",
  "role": "editor"
}
```

**Response**

```json
{
  "id": "usr_1234567890",
  "email": "user@example.com",
  "name": "Jane Doe",
  "role": "editor",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `400 Bad Request`: Invalid input data
- `404 Not Found`: User not found

#### DELETE /users/{user_id}

Deletes a user.

**Parameters**

- `user_id` (string, required): The unique identifier of the user

**Response**

```json
{
  "message": "User deleted successfully"
}
```

**Error Responses**

- `404 Not Found`: User not found

### Products

#### GET /products

Retrieves a list of products.

**Query Parameters**

- `page` (integer, optional, default: 1): Page number
- `limit` (integer, optional, default: 10): Items per page
- `category` (string, optional): Filter by category
- `search` (string, optional): Search term

**Response**

```json
{
  "data": [
    {
      "id": "prod_1234567890",
      "name": "Product Name",
      "description": "Product description",
      "price": 29.99,
      "category": "electronics",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 100,
    "total_pages": 10
  }
}
```

#### POST /products

Creates a new product.

**Request Body**

```json
{
  "name": "New Product",
  "description": "Product description",
  "price": 49.99,
  "category": "electronics",
  "stock": 100
}
```

**Response**

```json
{
  "id": "prod_1234567890",
  "name": "New Product",
  "description": "Product description",
  "price": 49.99,
  "category": "electronics",
  "stock": 100,
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `400 Bad Request`: Invalid input data

#### GET /products/{product_id}

Retrieves a product by ID.

**Parameters**

- `product_id` (string, required): The unique identifier of the product

**Response**

```json
{
  "id": "prod_1234567890",
  "name": "Product Name",
  "description": "Product description",
  "price": 29.99,
  "category": "electronics",
  "stock": 50,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `404 Not Found`: Product not found

#### PUT /products/{product_id}

Updates an existing product.

**Parameters**

- `product_id` (string, required): The unique identifier of the product

**Request Body**

```json
{
  "price": 39.99,
  "stock": 75
}
```

**Response**

```json
{
  "id": "prod_1234567890",
  "name": "Product Name",
  "description": "Product description",
  "price": 39.99,
  "category": "electronics",
  "stock": 75,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `400 Bad Request`: Invalid input data
- `404 Not Found`: Product not found

#### DELETE /products/{product_id}

Deletes a product.

**Parameters**

- `product_id` (string, required): The unique identifier of the product

**Response**

```json
{
  "message": "Product deleted successfully"
}
```

**Error Responses**

- `404 Not Found`: Product not found

### Orders

#### POST /orders

Creates a new order.

**Request Body**

```json
{
  "user_id": "usr_1234567890",
  "items": [
    {
      "product_id": "prod_1234567890",
      "quantity": 2
    }
  ],
  "shipping_address": {
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "country": "USA"
  }
}
```

**Response**

```json
{
  "id": "ord_1234567890",
  "user_id": "usr_1234567890",
  "items": [
    {
      "product_id": "prod_1234567890",
      "quantity": 2,
      "unit_price": 29.99,
      "total_price": 59.98
    }
  ],
  "total_amount": 59.98,
  "status": "pending",
  "shipping_address": {
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "country": "USA"
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `400 Bad Request`: Invalid input data
- `404 Not Found`: User or product not found

#### GET /orders/{order_id}

Retrieves an order by ID.

**Parameters**

- `order_id` (string, required): The unique identifier of the order

**Response**

```json
{
  "id": "ord_1234567890",
  "user_id": "usr_1234567890",
  "items": [
    {
      "product_id": "prod_1234567890",
      "quantity": 2,
      "unit_price": 29.99,
      "total_price": 59.98
    }
  ],
  "total_amount": 59.98,
  "status": "shipped",
  "shipping_address": {
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "country": "USA"
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `404 Not Found`: Order not found

#### PUT /orders/{order_id}/status

Updates the status of an order.

**Parameters**

- `order_id` (string, required): The unique identifier of the order

**Request Body**

```json
{
  "status": "shipped"
}
```

**Response**

```json
{
  "id": "ord_1234567890",
  "status": "shipped",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**

- `400 Bad Request`: Invalid status value
- `404 Not Found`: Order not found

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

### Common Error Codes

| HTTP Status | Code | Description |
|------------|------|-------------|
| 400 | VALIDATION_ERROR | Invalid request data |
| 401 | UNAUTHORIZED | Missing or invalid authentication |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource not found |
| 409 | CONFLICT | Resource conflict |
| 429 | RATE_LIMIT_EXCEEDED | Too many requests |
| 500 | INTERNAL_ERROR | Internal server error |

## Rate Limiting

API requests are rate-limited. Limits are applied per API token.

- Standard tier: 1000 requests per hour
- Premium tier: 10000 requests per hour

Rate limit headers are included in all responses:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1704067200
```

## Pagination

List endpoints support pagination with the following parameters:

- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)

Pagination metadata is included in responses:

```json
{
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 100,
    "total_pages": 10
  }
}
```

## Versioning

The API is versioned through the URL path. The current version is `v1`.

## Changelog

### v1.0.0 (2024-01-01)

- Initial release
- User management endpoints
- Product management endpoints
- Order management endpoints