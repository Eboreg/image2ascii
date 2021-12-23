import os
import shelve
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Union
from uuid import uuid4

from image2ascii.config import Config

KEEP_DAYS = 7


class Session:
    uuid: str

    def __init__(
        self,
        uuid: str,
        filename: Union[str, Path],
        config: Config,
        keep_file=False,
        hash: Optional[int] = None
    ):
        self.datetime = datetime.now()
        self.uuid = uuid
        self.filename = filename
        self.config = config
        self.keep_file = keep_file
        self.hash = hash


class BaseDB:
    def get(self, uuid: str) -> Session:
        raise NotImplementedError

    def get_by_hash(self, hash: int) -> Optional[Session]:
        raise NotImplementedError

    def create(self, filename: Union[str, Path], config: Config, keep_file=False) -> Session:
        raise NotImplementedError

    def update(self, uuid: str, config: Config) -> Session:
        raise NotImplementedError

    def purge(self):
        raise NotImplementedError


class ShelfDB(BaseDB):
    def __init__(self, filename="image2ascii_db"):
        self.filename = filename
        with shelve.open(self.filename) as shelf:
            if "sessions" not in shelf:
                shelf["sessions"] = {}

    def get(self, uuid: str) -> Session:
        """May raise KeyError"""
        with shelve.open(self.filename) as shelf:
            return shelf["sessions"][uuid]

    def get_by_hash(self, hash: int) -> Optional[Session]:
        with shelve.open(self.filename) as shelf:
            try:
                return [s for s in shelf["sessions"].values() if s.hash == hash][0]
            except IndexError:
                return None

    def create(
        self,
        filename: Union[str, Path],
        config: Config,
        keep_file=False,
        hash: Optional[int] = None,
    ) -> Session:
        session = Session(str(uuid4()), filename, config, keep_file=keep_file, hash=hash)

        with shelve.open(self.filename) as shelf:
            sessions = shelf["sessions"]
            sessions[session.uuid] = session
            shelf["sessions"] = sessions

        self.purge()
        return session

    def update(self, uuid: str, config: Config) -> Session:
        with shelve.open(self.filename) as shelf:
            sessions: Dict[str, Session] = shelf["sessions"]
            # May raise KeyError:
            session = sessions[uuid]
            if session.config != config:
                # If config changed, make a new session with new uuid
                uuid = str(uuid4())
                session = Session(uuid, session.filename, config, keep_file=session.keep_file, hash=session.hash)
                sessions[uuid] = session
                shelf["sessions"] = sessions
        self.purge()
        return session

    def purge(self):
        with shelve.open(self.filename) as shelf:
            old_files = set([s.filename for s in shelf["sessions"].values() if not s.keep_file])
            sessions = {}

            for k, v in shelf["sessions"].items():
                if v.datetime >= (datetime.now() - timedelta(days=KEEP_DAYS)):
                    sessions[k] = v
                    if v.filename in old_files:
                        old_files.remove(v.filename)

            for filename in old_files:
                try:
                    os.remove(filename)
                except Exception:
                    pass

            shelf["sessions"] = sessions
