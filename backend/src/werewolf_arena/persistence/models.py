"""SQLite 权威状态表。"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有持久化表的基类。"""


class RoomRow(Base):
    __tablename__ = "rooms"
    room_id: Mapped[str] = mapped_column(String, primary_key=True)


class SnapshotRow(Base):
    __tablename__ = "game_snapshots"
    room_id: Mapped[str] = mapped_column(String, primary_key=True)
    state_json: Mapped[str] = mapped_column(Text)


class EventRow(Base):
    __tablename__ = "game_events"
    room_id: Mapped[str] = mapped_column(String, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_json: Mapped[str] = mapped_column(Text)
