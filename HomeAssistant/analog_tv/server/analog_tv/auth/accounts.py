"""Single local Admin account, created atomically in the existing database."""
from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from analog_tv.db.database import Base, Database


class AdminAccount(Base):
    __tablename__ = "admin_account"
    __table_args__ = (CheckConstraint("id = 1"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(110))


def read_account():
    with Database.instance().session() as db:
        account = db.get(AdminAccount, 1)
        return (account.username, account.password_hash) if account else None


def create_account(username, password_hash):
    with Database.instance().session() as db:
        db.add(AdminAccount(id=1, username=username, password_hash=password_hash))
        try:
            db.commit()
        except IntegrityError:
            return False
        return True
