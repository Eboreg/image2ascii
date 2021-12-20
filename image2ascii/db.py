import shelve
from datetime import datetime, timedelta
from typing import Optional, Union
from uuid import uuid4

from PIL.Image import Image

from image2ascii.config import Config
from image2ascii.core import Image2ASCII

KEEP_DAYS = 7


class BaseDBItem:
    def __init__(self, pk: Union[str, int]):
        self.datetime = datetime.now()
        self.pk = pk


class ImageDBItem(BaseDBItem):
    """Image is identified by hash of its getdata()"""
    def __init__(self, image: Image):
        self.image = image
        super().__init__(hash(tuple(image.getdata())))


class SessionDBItem(BaseDBItem):
    """pk = session uuid"""
    def __init__(self, pk: str, image_id: Union[str, int], config: Config):
        self.image_id = image_id
        self.config = config
        super().__init__(pk)


class BaseDB:
    def get_i2a(self, uuid: Optional[str]) -> Optional[Image2ASCII]:
        raise NotImplementedError

    def save_i2a(self, i2a: Image2ASCII, uuid: Optional[str] = None) -> Optional[str]:
        raise NotImplementedError

    def purge(self):
        raise NotImplementedError


class ShelfDB(BaseDB):
    def __init__(self, filename="image2ascii_db"):
        self.filename = filename
        with shelve.open(self.filename) as shelf:
            if "sessions" not in shelf:
                shelf["sessions"] = {}
            if "images" not in shelf:
                shelf["images"] = {}

    def get_i2a(self, uuid: Optional[str]) -> Optional[Image2ASCII]:
        if uuid:
            with shelve.open(self.filename) as shelf:
                if uuid in shelf["sessions"]:
                    session = shelf["sessions"][uuid]
                    assert isinstance(session, SessionDBItem)
                    if session.image_id in shelf["images"]:
                        image = shelf["images"][session.image_id]
                        assert isinstance(image, ImageDBItem)
                        return Image2ASCII.reconstruct(image.image, session.config)
        return None

    def save_i2a(self, i2a: Image2ASCII, uuid: Optional[str] = None) -> Optional[str]:
        if i2a.image is not None:
            uuid = uuid or str(uuid4())
            image = ImageDBItem(i2a.image)
            session = SessionDBItem(uuid, image.pk, i2a.config)
            with shelve.open(self.filename) as shelf:
                # Grab existing data for manipulation
                sessions = shelf["sessions"]
                images = shelf["images"]

                if uuid in sessions:
                    # If config changed, make a new uuid
                    if sessions[uuid].config != session.config:
                        uuid = str(uuid4())
                        session.pk = uuid
                images[image.pk] = image
                sessions[session.pk] = session

                # Store stuff back
                shelf["sessions"] = sessions
                shelf["images"] = images
        self.purge()
        return uuid

    def purge(self):
        with shelve.open(self.filename) as shelf:
            # Grab existing data for manipulation
            sessions = shelf["sessions"]
            images = shelf["images"]

            # Purge old sessions
            sessions = {
                uuid: session for uuid, session in sessions.items()
                if session.datetime >= (datetime.now() - timedelta(days=KEEP_DAYS))
            }
            # Purge images that no longer are referred to by any session, by
            # replacing the images dict with the ones that still are
            images = {
                pk: image for pk, image in images.items()
                if pk in [session.image_id for session in sessions.values()]
            }

            # Store stuff back
            shelf["sessions"] = sessions
            shelf["images"] = images
