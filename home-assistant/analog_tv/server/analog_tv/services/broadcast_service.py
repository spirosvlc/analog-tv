from datetime import datetime, timezone
from sqlalchemy.orm import Session
from analog_tv.db.repositories import ChannelRepository

class BroadcastService:
    def __init__(self, session:Session): self.repository=ChannelRepository(session)
    def now(self, channel_id:int):
        channel=self.repository.get(channel_id)
        if channel is None: raise ValueError('Channel not found.')
        if not channel.items: return channel,None,0.0,False
        # HLS/IPTV items with no duration are live sources.
        timed=[i for i in channel.items if (i.duration_seconds or 0)>0]
        if not timed:
            return channel,channel.items[0],0.0,True
        total=sum(i.duration_seconds for i in timed)
        if total <= 0: return channel,timed[0],0.0,False
        epoch=channel.broadcast_epoch or channel.created_at or datetime.utcnow()
        now=datetime.utcnow()
        elapsed=max(0.0,(now-epoch).total_seconds()) % total
        cursor=0.0
        for item in timed:
            if elapsed < cursor + item.duration_seconds:
                return channel,item,max(0.0,elapsed-cursor),False
            cursor += item.duration_seconds
        return channel,timed[0],0.0,False
