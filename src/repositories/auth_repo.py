"""Authorization repository for managing user permissions and roles."""

from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import logging
from enum import Enum
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from src.exceptions import (
    AuthorizationError,
    RepositoryError,
    ValidationError,
    NotFoundError,
)
from src.models.user import User, UserRole, Permission
from src.database.connection import DatabaseConnection
from src.utils.validators import validate_uuid, validate_non_empty_string

logger = logging.getLogger(__name__)


class AuthorizationAction(Enum):
    """Enumeration of authorization actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class AuthorizationRule:
    """Data class representing an authorization rule."""
    id: UUID
    role: UserRole
    resource_type: str
    actions: Set[AuthorizationAction]
    conditions: Optional[Dict[str, object]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True


@dataclass
class AuthorizationContext:
    """Data class representing authorization context."""
    user_id: UUID
    roles: Set[UserRole]
    permissions: Set[Permission]
    resource_type: str
    resource_id: Optional[UUID] = None
    action: Optional[AuthorizationAction] = None
    attributes: Dict[str, object] = field(default_factory=dict)


class AuthorizationRepository:
    """Repository for managing authorization rules and permissions."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """Initialize the authorization repository.

        Args:
            db_connection: Database connection instance.

        Raises:
            RepositoryError: If database connection is invalid.
        """
        if not isinstance(db_connection, DatabaseConnection):
            raise RepositoryError("Invalid database connection provided")

        self._db = db_connection
        self._cache: Dict[str, List[AuthorizationRule]] = {}
        self._cache_ttl: timedelta = timedelta(minutes=5)
        self._cache_timestamps: Dict[str, datetime] = {}
        logger.info("AuthorizationRepository initialized")

    def _get_cache_key(self, role: UserRole, resource_type: str) -> str:
        """Generate cache key for authorization rules.

        Args:
            role: User role.
            resource_type: Type of resource.

        Returns:
            Cache key string.
        """
        return f"{role.value}:{resource_type}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid.

        Args:
            cache_key: Cache key to check.

        Returns:
            True if cache is valid, False otherwise.
        """
        if cache_key not in self._cache_timestamps:
            return False

        timestamp = self._cache_timestamps[cache_key]
        return datetime.utcnow() - timestamp < self._cache_ttl

    def _invalidate_cache(self, role: Optional[UserRole] = None,
                          resource_type: Optional[str] = None) -> None:
        """Invalidate cache entries.

        Args:
            role: Optional role to invalidate.
            resource_type: Optional resource type to invalidate.
        """
        if role and resource_type:
            cache_key = self._get_cache_key(role, resource_type)
            self._cache.pop(cache_key, None)
            self._cache_timestamps.pop(cache_key, None)
        elif role:
            keys_to_remove = [
                key for key in self._cache
                if key.startswith(role.value)
            ]
            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()

    def create_authorization_rule(self, rule: AuthorizationRule) -> AuthorizationRule:
        """Create a new authorization rule.

        Args:
            rule: Authorization rule to create.

        Returns:
            Created authorization rule.

        Raises:
            ValidationError: If rule data is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not isinstance(rule, AuthorizationRule):
                raise ValidationError("Invalid authorization rule object")

            if not rule.actions:
                raise ValidationError("Authorization rule must have at least one action")

            query = """
                INSERT INTO authorization_rules (
                    id, role, resource_type, actions, conditions,
                    created_at, updated_at, is_active
                ) VALUES (
                    %(id)s, %(role)s, %(resource_type)s, %(actions)s,
                    %(conditions)s, %(created_at)s, %(updated_at)s, %(is_active)s
                )
            """

            params = {
                "id": str(rule.id),
                "role": rule.role.value,
                "resource_type": rule.resource_type,
                "actions": [action.value for action in rule.actions],
                "conditions": rule.conditions,
                "created_at": rule.created_at,
                "updated_at": rule.updated_at,
                "is_active": rule.is_active,
            }

            self._db.execute(query, params)
            self._invalidate_cache(rule.role, rule.resource_type)

            logger.info(
                "Authorization rule created: %s for role %s on %s",
                rule.id,
                rule.role.value,
                rule.resource_type,
            )

            return rule

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to create authorization rule: %s", error)
            raise RepositoryError(f"Failed to create authorization rule: {error}") from error

    def get_rules_for_role(self, role: UserRole,
                           resource_type: Optional[str] = None) -> List[AuthorizationRule]:
        """Get authorization rules for a specific role.

        Args:
            role: User role to get rules for.
            resource_type: Optional resource type filter.

        Returns:
            List of authorization rules.

        Raises:
            ValidationError: If role is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not isinstance(role, UserRole):
                raise ValidationError("Invalid user role")

            cache_key = self._get_cache_key(role, resource_type or "*")

            if self._is_cache_valid(cache_key):
                logger.debug("Returning cached authorization rules for %s", cache_key)
                return self._cache[cache_key]

            if resource_type:
                query = """
                    SELECT * FROM authorization_rules
                    WHERE role = %(role)s
                    AND resource_type = %(resource_type)s
                    AND is_active = TRUE
                """
                params = {
                    "role": role.value,
                    "resource_type": resource_type,
                }
            else:
                query = """
                    SELECT * FROM authorization_rules
                    WHERE role = %(role)s
                    AND is_active = TRUE
                """
                params = {"role": role.value}

            results = self._db.fetch_all(query, params)
            rules = self._convert_to_rules(results)

            self._cache[cache_key] = rules
            self._cache_timestamps[cache_key] = datetime.utcnow()

            return rules

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to get authorization rules: %s", error)
            raise RepositoryError(f"Failed to get authorization rules: {error}") from error

    def check_permission(self, context: AuthorizationContext) -> bool:
        """Check if a user has permission to perform an action.

        Args:
            context: Authorization context containing user and action details.

        Returns:
            True if authorized, False otherwise.

        Raises:
            ValidationError: If context is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not isinstance(context, AuthorizationContext):
                raise ValidationError("Invalid authorization context")

            if not context.user_id:
                raise ValidationError("User ID is required in authorization context")

            if not context.action:
                raise ValidationError("Action is required in authorization context")

            # Check direct permissions first
            if context.permissions:
                for permission in context.permissions:
                    if self._check_direct_permission(permission, context):
                        logger.debug(
                            "User %s authorized via direct permission",
                            context.user_id,
                        )
                        return True

            # Check role-based rules
            for role in context.roles:
                rules = self.get_rules_for_role(role, context.resource_type)
                for rule in rules:
                    if self._evaluate_rule(rule, context):
                        logger.debug(
                            "User %s authorized via role %s rule",
                            context.user_id,
                            role.value,
                        )
                        return True

            logger.warning(
                "User %s not authorized for %s on %s",
                context.user_id,
                context.action.value,
                context.resource_type,
            )

            return False

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to check permission: %s", error)
            raise RepositoryError(f"Failed to check permission: {error}") from error

    def _check_direct_permission(self, permission: Permission,
                                  context: AuthorizationContext) -> bool:
        """Check if a direct permission grants access.

        Args:
            permission: Permission to check.
            context: Authorization context.

        Returns:
            True if permission grants access, False otherwise.
        """
        if permission.resource_type != context.resource_type:
            return False

        if permission.action != context.action.value:
            return False

        if permission.resource_id and permission.resource_id != context.resource_id:
            return False

        if permission.conditions:
            return self._evaluate_conditions(permission.conditions, context.attributes)

        return True

    def _evaluate_rule(self, rule: AuthorizationRule,
                       context: AuthorizationContext) -> bool:
        """Evaluate an authorization rule against a context.

        Args:
            rule: Authorization rule to evaluate.
            context: Authorization context.

        Returns:
            True if rule matches, False otherwise.
        """
        if context.action not in rule.actions:
            return False

        if rule.conditions:
            return self._evaluate_conditions(rule.conditions, context.attributes)

        return True

    def _evaluate_conditions(self, conditions: Dict[str, object],
                              attributes: Dict[str, object]) -> bool:
        """Evaluate authorization conditions.

        Args:
            conditions: Conditions to evaluate.
            attributes: Context attributes to evaluate against.

        Returns:
            True if conditions are met, False otherwise.
        """
        for key, value in conditions.items():
            if key not in attributes:
                return False

            attribute_value = attributes[key]

            if isinstance(value, dict):
                if "operator" in value and "value" in value:
                    operator = value["operator"]
                    expected_value = value["value"]

                    if operator == "eq":
                        if attribute_value != expected_value:
                            return False
                    elif operator == "neq":
                        if attribute_value == expected_value:
                            return False
                    elif operator == "gt":
                        if not (attribute_value > expected_value):
                            return False
                    elif operator == "gte":
                        if not (attribute_value >= expected_value):
                            return False
                    elif operator == "lt":
                        if not (attribute_value < expected_value):
                            return False
                    elif operator == "lte":
                        if not (attribute_value <= expected_value):
                            return False
                    elif operator == "in":
                        if attribute_value not in expected_value:
                            return False
                    elif operator == "not_in":
                        if attribute_value in expected_value:
                            return False
                    else:
                        logger.warning("Unknown operator: %s", operator)
                        return False
                else:
                    return False
            else:
                if attribute_value != value:
                    return False

        return True

    def _convert_to_rules(self, results: List[Dict]) -> List[AuthorizationRule]:
        """Convert database results to AuthorizationRule objects.

        Args:
            results: Database query results.

        Returns:
            List of AuthorizationRule objects.
        """
        rules = []
        for row in results:
            try:
                rule = AuthorizationRule(
                    id=UUID(row["id"]),
                    role=UserRole(row["role"]),
                    resource_type=row["resource_type"],
                    actions={AuthorizationAction(action) for action in row["actions"]},
                    conditions=row.get("conditions"),
                    created_at=row.get("created_at", datetime.utcnow()),
                    updated_at=row.get("updated_at", datetime.utcnow()),
                    is_active=row.get("is_active", True),
                )
                rules.append(rule)
            except (ValueError, KeyError) as error:
                logger.error("Failed to convert database row to rule: %s", error)
                continue

        return rules

    def update_authorization_rule(self, rule_id: UUID,
                                   updates: Dict[str, object]) -> AuthorizationRule:
        """Update an existing authorization rule.

        Args:
            rule_id: ID of the rule to update.
            updates: Dictionary of fields to update.

        Returns:
            Updated authorization rule.

        Raises:
            NotFoundError: If rule not found.
            ValidationError: If update data is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not validate_uuid(str(rule_id)):
                raise ValidationError("Invalid rule ID format")

            if not updates:
                raise ValidationError("No updates provided")

            # Fetch existing rule
            existing_rule = self.get_rule_by_id(rule_id)
            if not existing_rule:
                raise NotFoundError(f"Authorization rule not found: {rule_id}")

            # Validate updates
            allowed_fields = {"actions", "conditions", "is_active"}
            invalid_fields = set(updates.keys()) - allowed_fields
            if invalid_fields:
                raise ValidationError(f"Invalid fields for update: {invalid_fields}")

            # Prepare update query
            set_clauses = []
            params = {"id": str(rule_id)}

            if "actions" in updates:
                actions = updates["actions"]
                if not isinstance(actions, (list, set)):
                    raise ValidationError("Actions must be a list or set")
                set_clauses.append("actions = %(actions)s")
                params["actions"] = [
                    action.value if isinstance(action, AuthorizationAction) else action
                    for action in actions
                ]

            if "conditions" in updates:
                conditions = updates["conditions"]
                if conditions is not None and not isinstance(conditions, dict):
                    raise ValidationError("Conditions must be a dictionary or None")
                set_clauses.append("conditions = %(conditions)s")
                params["conditions"] = conditions

            if "is_active" in updates:
                is_active = updates["is_active"]
                if not isinstance(is_active, bool):
                    raise ValidationError("is_active must be a boolean")
                set_clauses.append("is_active = %(is_active)s")
                params["is_active"] = is_active

            set_clauses.append("updated_at = %(updated_at)s")
            params["updated_at"] = datetime.utcnow()

            query = f"""
                UPDATE authorization_rules
                SET {', '.join(set_clauses)}
                WHERE id = %(id)s
                RETURNING *
            """

            result = self._db.fetch_one(query, params)
            if not result:
                raise NotFoundError(f"Authorization rule not found: {rule_id}")

            updated_rule = self._convert_to_rules([result])[0]

            # Invalidate cache
            self._invalidate_cache(updated_rule.role, updated_rule.resource_type)

            logger.info("Authorization rule updated: %s", rule_id)

            return updated_rule

        except (NotFoundError, ValidationError):
            raise
        except Exception as error:
            logger.error("Failed to update authorization rule: %s", error)
            raise RepositoryError(f"Failed to update authorization rule: {error}") from error

    def get_rule_by_id(self, rule_id: UUID) -> Optional[AuthorizationRule]:
        """Get an authorization rule by its ID.

        Args:
            rule_id: ID of the rule to retrieve.

        Returns:
            Authorization rule if found, None otherwise.

        Raises:
            ValidationError: If rule ID is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not validate_uuid(str(rule_id)):
                raise ValidationError("Invalid rule ID format")

            query = """
                SELECT * FROM authorization_rules
                WHERE id = %(id)s
            """
            params = {"id": str(rule_id)}

            result = self._db.fetch_one(query, params)
            if not result:
                return None

            rules = self._convert_to_rules([result])
            return rules[0] if rules else None

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to get authorization rule: %s", error)
            raise RepositoryError(f"Failed to get authorization rule: {error}") from error

    def delete_authorization_rule(self, rule_id: UUID) -> bool:
        """Delete an authorization rule.

        Args:
            rule_id: ID of the rule to delete.

        Returns:
            True if deleted, False if not found.

        Raises:
            ValidationError: If rule ID is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not validate_uuid(str(rule_id)):
                raise ValidationError("Invalid rule ID format")

            # Get rule before deletion for cache invalidation
            rule = self.get_rule_by_id(rule_id)
            if not rule:
                return False

            query = """
                DELETE FROM authorization_rules
                WHERE id = %(id)s
            """
            params = {"id": str(rule_id)}

            self._db.execute(query, params)

            # Invalidate cache
            self._invalidate_cache(rule.role, rule.resource_type)

            logger.info("Authorization rule deleted: %s", rule_id)

            return True

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to delete authorization rule: %s", error)
            raise RepositoryError(f"Failed to delete authorization rule: {error}") from error

    def get_all_rules(self, page: int = 1, page_size: int = 50) -> Tuple[List[AuthorizationRule], int]:
        """Get all authorization rules with pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of rules, total count).

        Raises:
            ValidationError: If pagination parameters are invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if page < 1:
                raise ValidationError("Page must be greater than 0")
            if page_size < 1 or page_size > 100:
                raise ValidationError("Page size must be between 1 and 100")

            offset = (page - 1) * page_size

            count_query = "SELECT COUNT(*) as total FROM authorization_rules"
            count_result = self._db.fetch_one(count_query)
            total_count = count_result["total"] if count_result else 0

            query = """
                SELECT * FROM authorization_rules
                ORDER BY created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """
            params = {
                "limit": page_size,
                "offset": offset,
            }

            results = self._db.fetch_all(query, params)
            rules = self._convert_to_rules(results)

            return rules, total_count

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to get all authorization rules: %s", error)
            raise RepositoryError(f"Failed to get all authorization rules: {error}") from error

    def get_rules_for_resource(self, resource_type: str) -> List[AuthorizationRule]:
        """Get all authorization rules for a specific resource type.

        Args:
            resource_type: Type of resource.

        Returns:
            List of authorization rules.

        Raises:
            ValidationError: If resource type is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not validate_non_empty_string(resource_type):
                raise ValidationError("Resource type cannot be empty")

            query = """
                SELECT * FROM authorization_rules
                WHERE resource_type = %(resource_type)s
                AND is_active = TRUE
                ORDER BY created_at DESC
            """
            params = {"resource_type": resource_type}

            results = self._db.fetch_all(query, params)
            return self._convert_to_rules(results)

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to get rules for resource: %s", error)
            raise RepositoryError(f"Failed to get rules for resource: {error}") from error

    def bulk_create_rules(self, rules: List[AuthorizationRule]) -> List[AuthorizationRule]:
        """Create multiple authorization rules in a batch.

        Args:
            rules: List of authorization rules to create.

        Returns:
            List of created authorization rules.

        Raises:
            ValidationError: If rules list is invalid.
            RepositoryError: If database operation fails.
        """
        try:
            if not rules:
                raise ValidationError("Rules list cannot be empty")

            if not all(isinstance(rule, AuthorizationRule) for rule in rules):
                raise ValidationError("All items must be AuthorizationRule instances")

            created_rules = []
            for rule in rules:
                created_rule = self.create_authorization_rule(rule)
                created_rules.append(created_rule)

            logger.info("Bulk created %d authorization rules", len(created_rules))

            return created_rules

        except ValidationError:
            raise
        except Exception as error:
            logger.error("Failed to bulk create authorization rules: %s", error)
            raise RepositoryError(f"Failed to bulk create authorization rules: {error}") from error

    def clear_cache(self) -> None:
        """Clear the authorization rules cache."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Authorization rules cache cleared")

    def __repr__(self) -> str:
        """Return string representation of the repository."""
        return (
            f"AuthorizationRepository("
            f"db={self._db}, "
            f"cache_size={len(self._cache)}"
            f")"
        )