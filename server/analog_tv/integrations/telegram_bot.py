import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from analog_tv.db.database import Database
from analog_tv.domain.enums import AlertLevel
from analog_tv.domain.schemas import AlertCreate
from analog_tv.services.alert_service import AlertService
from analog_tv.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class TelegramAlertCommand:
    """Handles `/alert <level> <message>` Telegram commands."""

    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if update.effective_chat is None or update.message is None:
            return

        session = Database.instance().session()
        try:
            settings = SettingsService(session)
            allowed_chat_id = settings.get_value("telegram_chat_id")

            if (
                allowed_chat_id
                and str(update.effective_chat.id) != allowed_chat_id
            ):
                logger.warning(
                    "Rejected Telegram command from chat %s",
                    update.effective_chat.id,
                )
                return

            if len(context.args) < 2:
                await update.message.reply_text(
                    "Usage: /alert medium|serious|critical Your message"
                )
                return

            try:
                level = AlertLevel(context.args[0].lower())
            except ValueError:
                await update.message.reply_text(
                    "Level must be medium, serious, or critical."
                )
                return

            message = " ".join(context.args[1:]).strip()
            AlertService(session).create(
                AlertCreate(level=level, message=message)
            )

            await update.message.reply_text(
                f"Analog TV {level.value} alert published."
            )
        finally:
            session.close()


class TelegramBotWorker:
    """Owns the Telegram polling lifecycle."""

    def __init__(self) -> None:
        self.application: Application | None = None

    async def run(self) -> None:
        session = Database.instance().session()
        try:
            settings = SettingsService(session)
            enabled = (
                settings.get_value(
                    "telegram_enabled",
                    "false",
                ).lower()
                == "true"
            )
            token = settings.get_value("telegram_token")
        finally:
            session.close()

        if not enabled or not token:
            logger.info("Telegram integration is disabled.")
            return

        self.application = (
            Application.builder()
            .token(token)
            .build()
        )
        self.application.add_handler(
            CommandHandler(
                "alert",
                TelegramAlertCommand(),
            )
        )

        await self.application.initialize()
        await self.application.start()

        if self.application.updater is None:
            raise RuntimeError("Telegram updater was not initialized.")

        await self.application.updater.start_polling(
            drop_pending_updates=True
        )
        logger.info("Telegram bot started.")

        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
