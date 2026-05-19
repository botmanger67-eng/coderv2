"""
Telegram message handlers for the bot.

This module contains all message handlers for processing incoming Telegram messages,
including command handlers, callback query handlers, and message type handlers.
"""

import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

from src.bot.services import BotService
from src.bot.exceptions import (
    HandlerError,
    ServiceError,
    ValidationError,
    AuthorizationError,
)
from src.bot.models import User, Message, Command
from src.config import settings

logger = logging.getLogger(__name__)


class MessageHandlers:
    """Handles all Telegram message types and commands."""

    def __init__(self, bot_service: BotService):
        """
        Initialize message handlers.

        Args:
            bot_service: Bot service instance for business logic
        """
        self.bot_service = bot_service
        self._validate_service()

    def _validate_service(self) -> None:
        """Validate that the bot service is properly initialized."""
        if not self.bot_service:
            raise HandlerError("Bot service is required for message handlers")

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /start command.

        Args:
            update: Telegram update object
            context: Callback context

        Raises:
            HandlerError: If handler fails to process command
        """
        try:
            user = self._get_user(update)
            logger.info(f"Start command received from user {user.id}")

            welcome_message = (
                f"👋 Welcome {user.first_name}!\n\n"
                f"I'm your enterprise bot. Here's what I can do:\n"
                f"• /help - Show available commands\n"
                f"• /status - Check bot status\n"
                f"• /settings - Configure preferences\n\n"
                f"Feel free to send me a message!"
            )

            await update.message.reply_text(
                text=welcome_message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

            await self.bot_service.log_command(
                user_id=user.id,
                command=Command.START,
                timestamp=datetime.utcnow(),
            )

        except TelegramError as e:
            logger.error(f"Telegram error in start command: {e}")
            raise HandlerError(f"Failed to process start command: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in start command: {e}")
            raise HandlerError(f"Unexpected error: {e}")

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /help command.

        Args:
            update: Telegram update object
            context: Callback context

        Raises:
            HandlerError: If handler fails to process command
        """
        try:
            user = self._get_user(update)
            logger.info(f"Help command received from user {user.id}")

            help_text = (
                "📚 <b>Available Commands</b>\n\n"
                "/start - Start the bot\n"
                "/help - Show this help message\n"
                "/status - Check bot status\n"
                "/settings - Configure your settings\n"
                "/feedback - Send feedback\n\n"
                "<b>Tips:</b>\n"
                "• Send any text message for processing\n"
                "• Use inline buttons for quick actions\n"
                "• Contact support for assistance"
            )

            await update.message.reply_text(
                text=help_text,
                parse_mode=ParseMode.HTML,
            )

            await self.bot_service.log_command(
                user_id=user.id,
                command=Command.HELP,
                timestamp=datetime.utcnow(),
            )

        except TelegramError as e:
            logger.error(f"Telegram error in help command: {e}")
            raise HandlerError(f"Failed to process help command: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in help command: {e}")
            raise HandlerError(f"Unexpected error: {e}")

    async def status_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /status command.

        Args:
            update: Telegram update object
            context: Callback context

        Raises:
            HandlerError: If handler fails to process command
        """
        try:
            user = self._get_user(update)
            logger.info(f"Status command received from user {user.id}")

            bot_status = await self.bot_service.get_bot_status()
            user_status = await self.bot_service.get_user_status(user.id)

            status_message = (
                "📊 <b>Bot Status</b>\n\n"
                f"• Bot: {'✅ Online' if bot_status['online'] else '❌ Offline'}\n"
                f"• Uptime: {bot_status['uptime']}\n"
                f"• Active Users: {bot_status['active_users']}\n"
                f"• Messages Today: {bot_status['messages_today']}\n\n"
                f"<b>Your Status</b>\n"
                f"• Messages Sent: {user_status['messages_sent']}\n"
                f"• Commands Used: {user_status['commands_used']}\n"
                f"• Last Active: {user_status['last_active']}"
            )

            await update.message.reply_text(
                text=status_message,
                parse_mode=ParseMode.HTML,
            )

            await self.bot_service.log_command(
                user_id=user.id,
                command=Command.STATUS,
                timestamp=datetime.utcnow(),
            )

        except TelegramError as e:
            logger.error(f"Telegram error in status command: {e}")
            raise HandlerError(f"Failed to process status command: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in status command: {e}")
            raise HandlerError(f"Unexpected error: {e}")

    async def settings_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /settings command.

        Args:
            update: Telegram update object
            context: Callback context

        Raises:
            HandlerError: If handler fails to process command
        """
        try:
            user = self._get_user(update)
            logger.info(f"Settings command received from user {user.id}")

            user_settings = await self.bot_service.get_user_settings(user.id)

            keyboard = [
                [
                    InlineKeyboardButton(
                        "Notifications",
                        callback_data="settings_notifications"
                    ),
                    InlineKeyboardButton(
                        "Language",
                        callback_data="settings_language"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Privacy",
                        callback_data="settings_privacy"
                    ),
                    InlineKeyboardButton(
                        "Reset",
                        callback_data="settings_reset"
                    ),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            settings_message = (
                "⚙️ <b>Settings</b>\n\n"
                f"• Notifications: {'✅ On' if user_settings['notifications'] else '❌ Off'}\n"
                f"• Language: {user_settings['language']}\n"
                f"• Privacy Mode: {'✅ On' if user_settings['privacy_mode'] else '❌ Off'}\n\n"
                "Select an option below to modify:"
            )

            await update.message.reply_text(
                text=settings_message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )

            await self.bot_service.log_command(
                user_id=user.id,
                command=Command.SETTINGS,
                timestamp=datetime.utcnow(),
            )

        except TelegramError as e:
            logger.error(f"Telegram error in settings command: {e}")
            raise HandlerError(f"Failed to process settings command: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in settings command: {e}")
            raise HandlerError(f"Unexpected error: {e}")

    async def feedback_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /feedback command.

        Args:
            update: Telegram update object
            context: Callback context

        Raises:
            HandlerError: If handler fails to process command
        """
        try:
            user = self._get_user(update)
            logger.info(f"Feedback command received from user {user.id}")

            feedback_message = (
                "💬 <b>Send Feedback</b>\n\n"
                "Please reply to this message with your feedback.\n"
                "Your feedback helps us improve the bot!"
            )

            await update.message.reply_text(
                text=feedback_message,
                parse_mode=ParseMode.HTML,
            )

            # Set conversation state for feedback
            context.user_data['awaiting_feedback'] = True

            await self.bot_service.log_command(
                user_id=user.id,
                command=Command.FEEDBACK,
                timestamp=datetime.utcnow(),
            )

        except TelegramError as e:
            logger.error(f"Telegram error in feedback command: {e}")
            raise HandlerError(f"Failed to process feedback command: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in feedback command: {e}")
            raise HandlerError(f"Unexpected error: {e}")

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming text messages.

        Args:
            update: Telegram update object
            context: Callback context

        Raises:
            HandlerError: If handler fails to process message
        """
        try:
            user = self._get_user(update)
            message_text = update.message.text

            if not message_text:
                logger.warning(f"Empty message received from user {user.id}")
                return

            logger.info(f"Text message received from user {user.id}: {message_text[:50]}...")

            # Check if awaiting feedback
            if context.user_data.get('awaiting_feedback'):
                await self._handle_feedback_response(update, context, user, message_text)
                return

            # Process regular message
            response = await self.bot_service.process_message(
                user_id=user.id,
                message=Message(
                    text=message_text,
                    timestamp=datetime.utcnow(),
                    message_type="text",
                ),
            )

            await update.message.reply_text(
                text=response.text,
                parse_mode=ParseMode.HTML,
                reply_markup=response.reply_markup,
            )

            await self.bot_service.log_message(
                user_id=user.id,
                message=message_text,
                timestamp=datetime.utcnow(),
            )

        except ValidationError as e:
            logger.warning(f"Validation error for user {user.id}: {e}")
            await update.message.reply_text(
                text=f"❌ Invalid input: {str(e)}",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            logger.error(f"Telegram error in text handler: {e}")
            raise HandlerError(f"Failed to process message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in text handler: {e}")
            raise HandlerError(f"Unexpected error: {e}")

    async def _handle_feedback_response(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user: User,
        feedback_text: str,
    ) -> None:
        """
        Handle feedback response from user.

        Args:
            update: Telegram update object
            context: Callback context
            user: User object
            feedback_text: Feedback text from user

        Raises:
            HandlerError: If handler fails to process feedback
        """
        try:
            logger.info(f"Processing feedback from user {user.id}")

            await self.bot_service.process_feedback(
                user_id=user.id,
                feedback_text=feedback_text,
                timestamp=datetime.utcnow(),
            )

            await update.message.reply_text(
                text="✅ Thank you for your feedback! We appreciate your input.",
                parse_mode=ParseMode.HTML,
            )

            # Clear feedback state
            context.user_data['awaiting_feedback'] = False

        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            await update.message.reply_text(
                text="❌ Sorry, there was an error processing your feedback. Please try again.",
                parse_mode=ParseMode.HTML,
            )
            context.user_data['awaiting_feedback'] = False

    async def handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle callback queries from inline keyboards.

        Args:
            update: Telegram update object
            context: Callback context

        Raises:
            HandlerError: If handler fails to process callback
        """
        try:
            query = update.callback_query
            await query.answer()

            user = self._get_user(update)
            callback_data = query.data

            logger.info(f"Callback query from user {user.id}: {callback_data}")

            # Process callback based on data prefix
            if callback_data.startswith("settings_"):
                await self._handle_settings_callback(update, context, user, callback_data)
            elif callback_data.startswith("action_"):
                await self._handle_action_callback(update, context, user, callback_data)
            else:
                logger.warning(f"Unknown callback data: {callback_data}")
                await query.edit_message_text(
                    text="❌ Unknown action. Please try again.",
                    parse_mode=ParseMode.HTML,
                )

        except TelegramError as e:
            logger.error(f"Telegram error in callback handler: {e}")
            raise HandlerError(f"Failed to process callback: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in callback handler: {e}")
            raise HandlerError(f"Unexpected error: {e}")

    async def _handle_settings_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user: User,
        callback_data: str,
    ) -> None:
        """
        Handle settings-related callback queries.

        Args:
            update: Telegram update object
            context: Callback context
            user: User object
            callback_data: Callback data string
        """
        try:
            query = update.callback_query
            setting_type = callback_data.replace("settings_", "")

            if setting_type == "notifications":
                new_state = await self.bot_service.toggle_notifications(user.id)
                await query.edit_message_text(
                    text=f"✅ Notifications {'enabled' if new_state else 'disabled'}",
                    parse_mode=ParseMode.HTML,
                )
            elif setting_type == "language":
                # Show language selection
                keyboard = [
                    [InlineKeyboardButton("English", callback_data="lang_en")],
                    [InlineKeyboardButton("Spanish", callback_data="lang_es")],
                    [InlineKeyboardButton("French", callback_data="lang_fr")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text="🌐 Select your language:",
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            elif setting_type == "privacy":
                new_state = await self.bot_service.toggle_privacy_mode(user.id)
                await query.edit_message_text(
                    text=f"🔒 Privacy mode {'enabled' if new_state else 'disabled'}",
                    parse_mode=ParseMode.HTML,
                )
            elif setting_type == "reset":
                await self.bot_service.reset_settings(user.id)
                await query.edit_message_text(
                    text="🔄 Settings have been reset to defaults.",
                    parse_mode=ParseMode.HTML,
                )

        except Exception as e:
            logger.error(f"Error handling settings callback: {e}")
            await query.edit_message_text(
                text="❌ Error updating settings. Please try again.",
                parse_mode=ParseMode.HTML,
            )

    async def _handle_action_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user: User,
        callback_data: str,
    ) -> None:
        """
        Handle action-related callback queries.

        Args:
            update: Telegram update object
            context: Callback context
            user: User object
            callback_data: Callback data string
        """
        try:
            query = update.callback_query
            action = callback_data.replace("action_", "")

            result = await self.bot_service.process_action(
                user_id=user.id,
                action=action,
                timestamp=datetime.utcnow(),
            )

            await query.edit_message_text(
                text=result.message,
                parse_mode=ParseMode.HTML,
                reply_markup=result.reply_markup,
            )

        except Exception as e:
            logger.error(f"Error handling action callback: {e}")
            await query.edit_message_text(
                text="❌ Error processing action. Please try again.",
                parse_mode=ParseMode.HTML,
            )

    async def handle_error(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle errors that occur during message processing.

        Args:
            update: Telegram update object
            context: Callback context
        """
        try:
            logger.error(f"Update {update.update_id} caused error {context.error}")

            if update and update.effective_message:
                await update.effective_message.reply_text(
                    text="❌ An error occurred while processing your request. "
                         "Please try again later or contact support.",
                    parse_mode=ParseMode.HTML,
                )

        except Exception as e:
            logger.error(f"Error in error handler: {e}")

    def _get_user(self, update: Update) -> User:
        """
        Extract user information from update.

        Args:
            update: Telegram update object

        Returns:
            User object with user information

        Raises:
            ValidationError: If user information is missing
        """
        try:
            if update.effective_user:
                return User(
                    id=update.effective_user.id,
                    first_name=update.effective_user.first_name or "",
                    last_name=update.effective_user.last_name or "",
                    username=update.effective_user.username or "",
                    language_code=update.effective_user.language_code or "en",
                )
            raise ValidationError("No user information found in update")
        except AttributeError as e:
            raise ValidationError(f"Invalid update structure: {e}")

    def get_handlers(self) -> list:
        """
        Get all message handlers for registration.

        Returns:
            List of handler objects
        """
        return [
            CommandHandler("start", self.start_command),
            CommandHandler("help", self.help_command),
            CommandHandler("status", self.status_command),
            CommandHandler("settings", self.settings_command),
            CommandHandler("feedback", self.feedback_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message),
            CallbackQueryHandler(self.handle_callback_query),
        ]