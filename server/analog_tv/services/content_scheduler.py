import asyncio, logging
from datetime import datetime, timedelta
from analog_tv.db.database import Database
from analog_tv.domain.enums import AlertLevel
from analog_tv.domain.schemas import AlertCreate
from analog_tv.integrations.feeds import RssNewsProvider, EmyWarningProvider
from analog_tv.services.alert_service import AlertService
from analog_tv.services.settings_service import SettingsService
logger=logging.getLogger(__name__)

class BroadcastContentScheduler:
    def __init__(self): self.news=RssNewsProvider(); self.emy=EmyWarningProvider()
    async def run(self):
        while True:
            try: await self.tick()
            except Exception: logger.exception('Broadcast content scheduler tick failed')
            await asyncio.sleep(60)
    async def tick(self):
        s=Database.instance().session()
        try:
            settings=SettingsService(s); now=datetime.utcnow()
            if settings.get_value('news_enabled','false')=='true': await self._news(settings,s,now)
            if settings.get_value('emy_enabled','false')=='true': await self._emy(settings,s,now)
        finally:s.close()
    def _due(self,value,minutes,now):
        if not value:return True
        try:return now-datetime.fromisoformat(value)>=timedelta(minutes=minutes)
        except ValueError:return True
    async def _news(self,settings,s,now):
        interval=int(settings.get_value('news_interval_minutes','60'))
        if not self._due(settings.get_value('news_last_shown'),interval,now):return
        url=settings.get_value('news_rss_url','https://www.ertnews.gr/feed/'); limit=int(settings.get_value('news_headlines','5'))
        headlines=await self.news.headlines(url,limit)
        if headlines:
            AlertService(s).create(AlertCreate(level=AlertLevel.MEDIUM,message='[ERT NEWS]  '+'  •  '.join(headlines)))
            settings.set_value('news_last_shown',now.isoformat())
    async def _emy(self,settings,s,now):
        check=int(settings.get_value('emy_interval_minutes','15'))
        if not self._due(settings.get_value('emy_last_checked'),check,now):return
        settings.set_value('emy_last_checked',now.isoformat())
        warning=await self.emy.warning(settings.get_value('emy_warnings_url','https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-greece'),settings.get_value('emy_region','Attica'))
        if not warning:return
        last_hash=settings.get_value('emy_last_hash'); last_shown=settings.get_value('emy_last_shown'); repeat=int(settings.get_value('emy_repeat_minutes','60'))
        if warning['hash'] != last_hash or self._due(last_shown,repeat,now):
            AlertService(s).create(AlertCreate(level=AlertLevel.MEDIUM,message='[ΕΜΥ]  '+warning['text']))
            settings.set_value('emy_last_hash',warning['hash']); settings.set_value('emy_last_shown',now.isoformat())
