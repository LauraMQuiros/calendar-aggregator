"""Database models for the Calendar Aggregator system."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class WebsiteStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNREACHABLE = "unreachable"
    ERROR = "error"


class Website(Base):
    __tablename__ = "websites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    folder_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("folders.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=WebsiteStatus.ACTIVE.value)
    extraction_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_extraction_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    folder: Mapped[Optional["Folder"]] = relationship("Folder", back_populates="websites")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="websites")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="website", cascade="all, delete-orphan")
    extraction_logs: Mapped[list["ExtractionLog"]] = relationship(
        "ExtractionLog", back_populates="website", cascade="all, delete-orphan"
    )


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("folders.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parent: Mapped[Optional["Folder"]] = relationship("Folder", back_populates="subfolders", remote_side="Folder.id")
    subfolders: Mapped[list["Folder"]] = relationship("Folder", back_populates="parent")
    websites: Mapped[list["Website"]] = relationship("Website", back_populates="folder")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="folders")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # ISO date or free-form
    start_time: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    original_language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    website_id: Mapped[int] = mapped_column(Integer, ForeignKey("websites.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    website: Mapped["Website"] = relationship("Website", back_populates="events")


class ExtractionLog(Base):
    __tablename__ = "extraction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    website_id: Mapped[int] = mapped_column(Integer, ForeignKey("websites.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    events_extracted: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    website: Mapped["Website"] = relationship("Website", back_populates="extraction_logs")


class ContentCache(Base):
    """Stores content hashes for cache/change detection."""

    __tablename__ = "content_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    folders: Mapped[list["Folder"]] = relationship("Folder", back_populates="user")
    websites: Mapped[list["Website"]] = relationship("Website", back_populates="user")


def init_db(database_url: str = "sqlite:///calendar_aggregator.db"):
    """Create database engine and tables."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    return engine
