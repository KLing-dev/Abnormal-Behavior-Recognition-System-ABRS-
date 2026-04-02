import uuid
from datetime import datetime
from typing import Optional


def generate_message_id() -> str:
    return str(uuid.uuid4())


def get_current_time() -> datetime:
    return datetime.now()


def format_time(dt: Optional[datetime] = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def parse_time(time_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    try:
        return datetime.strptime(time_str, fmt)
    except ValueError:
        return None
