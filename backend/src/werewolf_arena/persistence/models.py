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


class PlayerSessionRow(Base):
    """One opaque local-browser credential, stored only as a SHA-256 digest."""

    __tablename__ = "player_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    room_id: Mapped[str] = mapped_column(String, index=True)
    participant_id: Mapped[str] = mapped_column(String)


class AgentRunRow(Base):
    """Redacted per-attempt metadata for model operational accounting."""

    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    room_id: Mapped[str] = mapped_column(String, index=True)
    attempt_index: Mapped[int] = mapped_column(Integer)
    record_json: Mapped[str] = mapped_column(Text)
