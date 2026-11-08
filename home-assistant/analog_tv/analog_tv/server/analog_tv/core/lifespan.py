import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from analog_tv.db.database import Database
from analog_tv.integrations.telegram_bot import TelegramBotWorker
from analog_tv.services.content_scheduler import BroadcastContentScheduler
logger=logging.getLogger(__name__)
@asynccontextmanager
async def application_lifespan(app:FastAPI):
    db=Database.instance(); db.create_schema()
    telegram=TelegramBotWorker(); scheduler=BroadcastContentScheduler()
    tasks=[asyncio.create_task(telegram.run()),asyncio.create_task(scheduler.run())]
    app.state.database=db; app.state.telegram_worker=telegram; app.state.content_scheduler=scheduler
    try:yield
    finally:
        for t in tasks:t.cancel()
        for t in tasks:
            try:await t
            except asyncio.CancelledError:pass
