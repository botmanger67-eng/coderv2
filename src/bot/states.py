"""
Conversation states for the Telegram bot.

This module defines the finite state machine (FSM) states used
throughout the bot's conversation flows. Each state represents a
specific step in a multi-step interaction with the user.
"""

from enum import Enum, auto
from typing import Final


class ConversationState(Enum):
    """
    Enumeration of all possible conversation states.

    Each member represents a distinct state in the bot's FSM,
    enabling structured multi-step interactions.
    """

    # ── Authentication & Onboarding ──────────────────────────────────────
    AWAITING_EMAIL = auto()
    """Waiting for user to provide their email address."""

    AWAITING_VERIFICATION_CODE = auto()
    """Waiting for user to enter the verification code sent to their email."""

    AWAITING_PASSWORD = auto()
    """Waiting for user to set or enter their password."""

    AWAITING_PROFILE_NAME = auto()
    """Waiting for user to provide their display name."""

    # ── Main Menu Navigation ─────────────────────────────────────────────
    MAIN_MENU = auto()
    """User is viewing the main menu and can select an option."""

    # ── Ticket Creation ──────────────────────────────────────────────────
    AWAITING_TICKET_SUBJECT = auto()
    """Waiting for user to enter the ticket subject."""

    AWAITING_TICKET_DESCRIPTION = auto()
    """Waiting for user to enter the ticket description."""

    AWAITING_TICKET_PRIORITY = auto()
    """Waiting for user to select ticket priority (low, medium, high, critical)."""

    AWAITING_TICKET_CATEGORY = auto()
    """Waiting for user to select or enter ticket category."""

    AWAITING_TICKET_ATTACHMENT = auto()
    """Waiting for user to optionally attach a file to the ticket."""

    AWAITING_TICKET_CONFIRMATION = auto()
    """Waiting for user to confirm or cancel the ticket creation."""

    # ── Ticket Viewing & Management ──────────────────────────────────────
    VIEWING_TICKET_LIST = auto()
    """User is browsing a paginated list of tickets."""

    VIEWING_TICKET_DETAILS = auto()
    """User is viewing the details of a specific ticket."""

    AWAITING_TICKET_COMMENT = auto()
    """Waiting for user to add a comment to a ticket."""

    AWAITING_TICKET_STATUS_CHANGE = auto()
    """Waiting for user to select a new status for the ticket."""

    AWAITING_TICKET_ASSIGNEE = auto()
    """Waiting for user to select an assignee for the ticket."""

    # ── Search & Filter ──────────────────────────────────────────────────
    AWAITING_SEARCH_QUERY = auto()
    """Waiting for user to enter a search term."""

    AWAITING_FILTER_CRITERIA = auto()
    """Waiting for user to specify filter criteria (e.g., status, priority)."""

    # ── Settings & Profile ───────────────────────────────────────────────
    AWAITING_SETTINGS_OPTION = auto()
    """Waiting for user to select a settings option to modify."""

    AWAITING_NOTIFICATION_PREFERENCE = auto()
    """Waiting for user to set notification preferences."""

    AWAITING_LANGUAGE_SELECTION = auto()
    """Waiting for user to select their preferred language."""

    # ── Feedback & Support ───────────────────────────────────────────────
    AWAITING_FEEDBACK_TEXT = auto()
    """Waiting for user to enter their feedback message."""

    AWAITING_SUPPORT_MESSAGE = auto()
    """Waiting for user to describe their support issue."""

    # ── Administrative States ────────────────────────────────────────────
    AWAITING_ADMIN_COMMAND = auto()
    """Waiting for an admin to enter a command."""

    AWAITING_USER_MANAGEMENT_ACTION = auto()
    """Waiting for admin to select a user management action (ban, unban, promote)."""

    AWAITING_SYSTEM_ANNOUNCEMENT = auto()
    """Waiting for admin to enter a system-wide announcement message."""

    # ── Idle / Fallback ──────────────────────────────────────────────────
    IDLE = auto()
    """No active conversation; bot is waiting for any command."""

    # ── Error Recovery ───────────────────────────────────────────────────
    AWAITING_RETRY_OR_CANCEL = auto()
    """Waiting for user to retry the last action or cancel the operation."""

    def __str__(self) -> str:
        """
        Return a human-readable representation of the state.

        Returns:
            str: The state name in lowercase with underscores replaced by spaces.
        """
        return self.name.lower().replace("_", " ")

    @classmethod
    def from_string(cls, state_name: str) -> "ConversationState":
        """
        Convert a string to a ConversationState, with error handling.

        Args:
            state_name: The name of the state (case-insensitive).

        Returns:
            The corresponding ConversationState member.

        Raises:
            ValueError: If the state_name does not match any known state.
        """
        try:
            return cls[state_name.upper().replace(" ", "_")]
        except KeyError as exc:
            valid_states = ", ".join(member.name for member in cls)
            raise ValueError(
                f"Unknown state: '{state_name}'. Valid states are: {valid_states}"
            ) from exc


# ── Constants for state transitions ──────────────────────────────────────
STATE_TRANSITIONS: Final[dict[ConversationState, list[ConversationState]]] = {
    ConversationState.IDLE: [
        ConversationState.AWAITING_EMAIL,
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_ADMIN_COMMAND,
    ],
    ConversationState.AWAITING_EMAIL: [
        ConversationState.AWAITING_VERIFICATION_CODE,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_VERIFICATION_CODE: [
        ConversationState.AWAITING_PASSWORD,
        ConversationState.AWAITING_PROFILE_NAME,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_PASSWORD: [
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_PROFILE_NAME: [
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.MAIN_MENU: [
        ConversationState.AWAITING_TICKET_SUBJECT,
        ConversationState.VIEWING_TICKET_LIST,
        ConversationState.AWAITING_SEARCH_QUERY,
        ConversationState.AWAITING_SETTINGS_OPTION,
        ConversationState.AWAITING_FEEDBACK_TEXT,
        ConversationState.AWAITING_SUPPORT_MESSAGE,
        ConversationState.AWAITING_ADMIN_COMMAND,
        ConversationState.IDLE,
    ],
    ConversationState.AWAITING_TICKET_SUBJECT: [
        ConversationState.AWAITING_TICKET_DESCRIPTION,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_TICKET_DESCRIPTION: [
        ConversationState.AWAITING_TICKET_PRIORITY,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_TICKET_PRIORITY: [
        ConversationState.AWAITING_TICKET_CATEGORY,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_TICKET_CATEGORY: [
        ConversationState.AWAITING_TICKET_ATTACHMENT,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_TICKET_ATTACHMENT: [
        ConversationState.AWAITING_TICKET_CONFIRMATION,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_TICKET_CONFIRMATION: [
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.VIEWING_TICKET_LIST: [
        ConversationState.VIEWING_TICKET_DETAILS,
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_SEARCH_QUERY,
        ConversationState.AWAITING_FILTER_CRITERIA,
    ],
    ConversationState.VIEWING_TICKET_DETAILS: [
        ConversationState.VIEWING_TICKET_LIST,
        ConversationState.AWAITING_TICKET_COMMENT,
        ConversationState.AWAITING_TICKET_STATUS_CHANGE,
        ConversationState.AWAITING_TICKET_ASSIGNEE,
        ConversationState.MAIN_MENU,
    ],
    ConversationState.AWAITING_TICKET_COMMENT: [
        ConversationState.VIEWING_TICKET_DETAILS,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_TICKET_STATUS_CHANGE: [
        ConversationState.VIEWING_TICKET_DETAILS,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_TICKET_ASSIGNEE: [
        ConversationState.VIEWING_TICKET_DETAILS,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_SEARCH_QUERY: [
        ConversationState.VIEWING_TICKET_LIST,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_FILTER_CRITERIA: [
        ConversationState.VIEWING_TICKET_LIST,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_SETTINGS_OPTION: [
        ConversationState.AWAITING_NOTIFICATION_PREFERENCE,
        ConversationState.AWAITING_LANGUAGE_SELECTION,
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_NOTIFICATION_PREFERENCE: [
        ConversationState.AWAITING_SETTINGS_OPTION,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_LANGUAGE_SELECTION: [
        ConversationState.AWAITING_SETTINGS_OPTION,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_FEEDBACK_TEXT: [
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_SUPPORT_MESSAGE: [
        ConversationState.MAIN_MENU,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_ADMIN_COMMAND: [
        ConversationState.AWAITING_USER_MANAGEMENT_ACTION,
        ConversationState.AWAITING_SYSTEM_ANNOUNCEMENT,
        ConversationState.MAIN_MENU,
        ConversationState.IDLE,
    ],
    ConversationState.AWAITING_USER_MANAGEMENT_ACTION: [
        ConversationState.AWAITING_ADMIN_COMMAND,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_SYSTEM_ANNOUNCEMENT: [
        ConversationState.AWAITING_ADMIN_COMMAND,
        ConversationState.AWAITING_RETRY_OR_CANCEL,
    ],
    ConversationState.AWAITING_RETRY_OR_CANCEL: [
        ConversationState.IDLE,
        ConversationState.MAIN_MENU,
    ],
}


def is_valid_transition(
    current_state: ConversationState, next_state: ConversationState
) -> bool:
    """
    Check if a transition from current_state to next_state is allowed.

    Args:
        current_state: The current conversation state.
        next_state: The desired next conversation state.

    Returns:
        True if the transition is defined in STATE_TRANSITIONS, False otherwise.
    """
    allowed_states = STATE_TRANSITIONS.get(current_state, [])
    return next_state in allowed_states


def get_allowed_transitions(
    state: ConversationState,
) -> list[ConversationState]:
    """
    Retrieve the list of states that can be transitioned to from the given state.

    Args:
        state: The current conversation state.

    Returns:
        A list of allowed next states. Returns an empty list if the state
        is not found in the transition map.
    """
    return STATE_TRANSITIONS.get(state, [])