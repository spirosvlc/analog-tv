from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from analog_tv.db.database import session_dependency

DatabaseSession = Annotated[Session, Depends(session_dependency)]
