import shelve
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from image2ascii.core import Image2ASCII

KEEP_DAYS = 7


class Session:
    def __init__(self, uuid: Optional[str] = None, i2a: Optional[Image2ASCII] = None):
        self.uuid = uuid or str(uuid4())
        self.i2a = i2a
        self.datetime = datetime.now()


class BaseDB:
    def get_session(self, uuid: str) -> Session:
        raise NotImplementedError

    def save_session(self, session: Session):
        raise NotImplementedError

    def purge_sessions(self):
        raise NotImplementedError


class ShelfDB(BaseDB):
    def __init__(self, filename="image2ascii_db"):
        self.filename = filename
        with shelve.open(self.filename) as shelf:
            if "sessions" not in shelf:
                shelf["sessions"] = {}

    def get_session(self, uuid: str) -> Session:
        """Raises KeyError if not found"""
        with shelve.open(self.filename) as shelf:
            return shelf["sessions"][uuid]

    def save_session(self, session: Session):
        with shelve.open(self.filename) as shelf:
            sessions = shelf["sessions"]
            sessions[session.uuid] = session
            shelf["sessions"] = sessions

    def purge_sessions(self):
        with shelve.open(self.filename) as shelf:
            shelf["sessions"] = {
                uuid: session for uuid, session in shelf["sessions"].items()
                if session.datetime >= (datetime.now() - timedelta(days=KEEP_DAYS))
            }
