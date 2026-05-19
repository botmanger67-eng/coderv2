"""
Inline keyboard definitions for the Telegram bot.

This module provides factory functions for creating inline keyboards
used throughout the bot's conversation flows and menu systems.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode


@dataclass(frozen=True)
class ButtonConfig:
    """Configuration for a single inline keyboard button."""
    text: str
    callback_data: Optional[str] = None
    url: Optional[str] = None
    login_url: Optional[Dict[str, Any]] = None
    switch_inline_query: Optional[str] = None
    switch_inline_query_current_chat: Optional[str] = None
    callback_game: Optional[Dict[str, Any]] = None
    pay: bool = False

    def __post_init__(self) -> None:
        """Validate button configuration."""
        if not self.text:
            raise ValueError("Button text cannot be empty")
        if self.callback_data and len(self.callback_data) > 64:
            raise ValueError("Callback data exceeds 64 character limit")
        if self.url and len(self.url) > 512:
            raise ValueError("URL exceeds 512 character limit")


def _create_button(config: ButtonConfig) -> InlineKeyboardButton:
    """
    Create an InlineKeyboardButton from configuration.

    Args:
        config: Button configuration object.

    Returns:
        Configured InlineKeyboardButton instance.

    Raises:
        ValueError: If button configuration is invalid.
    """
    try:
        button_kwargs: Dict[str, Any] = {"text": config.text}

        if config.callback_data is not None:
            button_kwargs["callback_data"] = config.callback_data
        if config.url is not None:
            button_kwargs["url"] = config.url
        if config.login_url is not None:
            button_kwargs["login_url"] = config.login_url
        if config.switch_inline_query is not None:
            button_kwargs["switch_inline_query"] = config.switch_inline_query
        if config.switch_inline_query_current_chat is not None:
            button_kwargs["switch_inline_query_current_chat"] = config.switch_inline_query_current_chat
        if config.callback_game is not None:
            button_kwargs["callback_game"] = config.callback_game
        if config.pay:
            button_kwargs["pay"] = True

        return InlineKeyboardButton(**button_kwargs)
    except Exception as exc:
        raise ValueError(f"Failed to create button: {exc}") from exc


def _build_keyboard(
    buttons: List[List[ButtonConfig]],
) -> InlineKeyboardMarkup:
    """
    Build an inline keyboard markup from button configurations.

    Args:
        buttons: List of button rows, each row is a list of ButtonConfig.

    Returns:
        Configured InlineKeyboardMarkup instance.

    Raises:
        ValueError: If button configuration is empty or invalid.
    """
    if not buttons:
        raise ValueError("Keyboard must have at least one button row")

    try:
        keyboard: List[List[InlineKeyboardButton]] = []
        for row in buttons:
            if not row:
                raise ValueError("Each button row must contain at least one button")
            keyboard.append([_create_button(btn) for btn in row])
        return InlineKeyboardMarkup(keyboard)
    except Exception as exc:
        raise ValueError(f"Failed to build keyboard: {exc}") from exc


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Create the main menu inline keyboard.

    Returns:
        InlineKeyboardMarkup with main menu options.
    """
    buttons: List[List[ButtonConfig]] = [
        [
            ButtonConfig(text="📋 Start", callback_data="start"),
            ButtonConfig(text="ℹ️ Help", callback_data="help"),
        ],
        [
            ButtonConfig(text="⚙️ Settings", callback_data="settings"),
            ButtonConfig(text="📊 Stats", callback_data="stats"),
        ],
        [
            ButtonConfig(text="🔍 Search", callback_data="search"),
            ButtonConfig(text="📁 Files", callback_data="files"),
        ],
    ]
    return _build_keyboard(buttons)


def confirmation_keyboard(
    confirm_text: str = "✅ Confirm",
    cancel_text: str = "❌ Cancel",
    confirm_callback: str = "confirm",
    cancel_callback: str = "cancel",
) -> InlineKeyboardMarkup:
    """
    Create a confirmation/cancel inline keyboard.

    Args:
        confirm_text: Text for the confirm button.
        cancel_text: Text for the cancel button.
        confirm_callback: Callback data for the confirm button.
        cancel_callback: Callback data for the cancel button.

    Returns:
        InlineKeyboardMarkup with confirm and cancel buttons.
    """
    buttons: List[List[ButtonConfig]] = [
        [
            ButtonConfig(text=confirm_text, callback_data=confirm_callback),
            ButtonConfig(text=cancel_text, callback_data=cancel_callback),
        ]
    ]
    return _build_keyboard(buttons)


def pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str = "page",
    show_page_info: bool = True,
) -> InlineKeyboardMarkup:
    """
    Create a pagination inline keyboard.

    Args:
        current_page: Current page number (0-indexed).
        total_pages: Total number of pages.
        prefix: Prefix for callback data.
        show_page_info: Whether to show page number info.

    Returns:
        InlineKeyboardMarkup with pagination controls.

    Raises:
        ValueError: If page numbers are invalid.
    """
    if current_page < 0 or total_pages < 1:
        raise ValueError("Invalid page numbers")
    if current_page >= total_pages:
        raise ValueError("Current page exceeds total pages")

    buttons: List[List[ButtonConfig]] = [[]]

    if current_page > 0:
        buttons[0].append(
            ButtonConfig(
                text="⬅️ Previous",
                callback_data=f"{prefix}_prev_{current_page}",
            )
        )

    if show_page_info:
        buttons[0].append(
            ButtonConfig(
                text=f"📄 {current_page + 1}/{total_pages}",
                callback_data=f"{prefix}_info_{current_page}",
            )
        )

    if current_page < total_pages - 1:
        buttons[0].append(
            ButtonConfig(
                text="Next ➡️",
                callback_data=f"{prefix}_next_{current_page}",
            )
        )

    return _build_keyboard(buttons)


def url_keyboard(
    url: str,
    button_text: str = "🔗 Open Link",
    additional_buttons: Optional[List[ButtonConfig]] = None,
) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard with a URL button.

    Args:
        url: The URL to open.
        button_text: Text for the URL button.
        additional_buttons: Optional additional button rows.

    Returns:
        InlineKeyboardMarkup with URL button.

    Raises:
        ValueError: If URL is invalid.
    """
    if not url or len(url) > 512:
        raise ValueError("Invalid URL")

    buttons: List[List[ButtonConfig]] = [
        [ButtonConfig(text=button_text, url=url)]
    ]

    if additional_buttons:
        for row in additional_buttons:
            buttons.append([row] if not isinstance(row, list) else row)

    return _build_keyboard(buttons)


def multi_select_keyboard(
    options: List[str],
    selected: Optional[List[str]] = None,
    prefix: str = "select",
    max_per_row: int = 2,
) -> InlineKeyboardMarkup:
    """
    Create a multi-select inline keyboard.

    Args:
        options: List of option identifiers.
        selected: List of currently selected options.
        prefix: Prefix for callback data.
        max_per_row: Maximum buttons per row.

    Returns:
        InlineKeyboardMarkup with selectable options.

    Raises:
        ValueError: If options list is empty or max_per_row is invalid.
    """
    if not options:
        raise ValueError("Options list cannot be empty")
    if max_per_row < 1:
        raise ValueError("max_per_row must be at least 1")

    selected = selected or []
    buttons: List[List[ButtonConfig]] = []
    current_row: List[ButtonConfig] = []

    for option in options:
        is_selected = option in selected
        display_text = f"✅ {option}" if is_selected else f"⬜ {option}"
        callback = f"{prefix}_toggle_{option}"

        current_row.append(
            ButtonConfig(text=display_text, callback_data=callback)
        )

        if len(current_row) >= max_per_row:
            buttons.append(current_row)
            current_row = []

    if current_row:
        buttons.append(current_row)

    buttons.append([
        ButtonConfig(text="✅ Done", callback_data=f"{prefix}_done"),
        ButtonConfig(text="❌ Clear", callback_data=f"{prefix}_clear"),
    ])

    return _build_keyboard(buttons)


def settings_keyboard() -> InlineKeyboardMarkup:
    """
    Create settings menu inline keyboard.

    Returns:
        InlineKeyboardMarkup with settings options.
    """
    buttons: List[List[ButtonConfig]] = [
        [
            ButtonConfig(text="🔔 Notifications", callback_data="settings_notifications"),
            ButtonConfig(text="🌐 Language", callback_data="settings_language"),
        ],
        [
            ButtonConfig(text="🎨 Theme", callback_data="settings_theme"),
            ButtonConfig(text="🔒 Privacy", callback_data="settings_privacy"),
        ],
        [
            ButtonConfig(text="⬅️ Back", callback_data="back_to_main"),
        ],
    ]
    return _build_keyboard(buttons)


def help_keyboard() -> InlineKeyboardMarkup:
    """
    Create help menu inline keyboard.

    Returns:
        InlineKeyboardMarkup with help categories.
    """
    buttons: List[List[ButtonConfig]] = [
        [
            ButtonConfig(text="📖 Getting Started", callback_data="help_getting_started"),
            ButtonConfig(text="🔧 Commands", callback_data="help_commands"),
        ],
        [
            ButtonConfig(text="❓ FAQ", callback_data="help_faq"),
            ButtonConfig(text="📞 Contact Support", callback_data="help_support"),
        ],
        [
            ButtonConfig(text="⬅️ Back", callback_data="back_to_main"),
        ],
    ]
    return _build_keyboard(buttons)


def empty_keyboard() -> InlineKeyboardMarkup:
    """
    Create an empty inline keyboard (single button placeholder).

    Returns:
        InlineKeyboardMarkup with a placeholder button.
    """
    buttons: List[List[ButtonConfig]] = [
        [ButtonConfig(text="No actions available", callback_data="noop")]
    ]
    return _build_keyboard(buttons)