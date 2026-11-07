from collections.abc import Generator
from threading import Lock
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from analog_tv.core.config import get_settings

class Base(DeclarativeBase):
    pass

class Database:
    _instance: "Database | None" = None
    _lock = Lock()
    def __init__(self) -> None:
        settings=get_settings(); args={"check_same_thread":False} if settings.database_url.startswith("sqlite") else {}
        self.engine=create_engine(settings.database_url, connect_args=args)
        self.session_factory=sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None: cls._instance=cls()
        return cls._instance
    def create_schema(self) -> None:
        from analog_tv.db import models  # noqa
        Base.metadata.create_all(bind=self.engine)
        self._migrate_sqlite()
    def _migrate_sqlite(self):
        if self.engine.dialect.name != "sqlite": return
        inspector=inspect(self.engine)
        channel_cols={c['name'] for c in inspector.get_columns('channels')}
        item_cols={c['name'] for c in inspector.get_columns('channel_items')}
        with self.engine.begin() as conn:
            if 'broadcast_epoch' not in channel_cols:
                conn.execute(text("ALTER TABLE channels ADD COLUMN broadcast_epoch DATETIME"))
                conn.execute(text("UPDATE channels SET broadcast_epoch = created_at WHERE broadcast_epoch IS NULL"))
            additions={
                'duration_seconds': "ALTER TABLE channel_items ADD COLUMN duration_seconds FLOAT DEFAULT 0",
                'media_kind': "ALTER TABLE channel_items ADD COLUMN media_kind VARCHAR(30) DEFAULT 'video'",
                'provider_id': "ALTER TABLE channel_items ADD COLUMN provider_id VARCHAR(255)",
                'thumbnail_url': "ALTER TABLE channel_items ADD COLUMN thumbnail_url TEXT",
            }
            for col, sql in additions.items():
                if col not in item_cols: conn.execute(text(sql))
    def session(self)->Session: return self.session_factory()

def session_dependency()->Generator[Session,None,None]:
    session=Database.instance().session()
    try: yield session
    finally: session.close()
