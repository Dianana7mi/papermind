import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Library(Base):
    __tablename__ = "libraries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (UniqueConstraint("library_id", "sha256"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    extraction_lock: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    section: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int | None]
    text: Mapped[str] = mapped_column(Text)
    locator: Mapped[dict] = mapped_column(JSON, default=dict)


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        UniqueConstraint("paper_id", "fingerprint"),
        Index("ix_experiment_lookup", "owner_id", "model_name", "dataset_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(200), index=True)
    dataset_name: Mapped[str | None] = mapped_column(String(200), index=True)
    metric_name: Mapped[str | None] = mapped_column(String(100), index=True)
    record: Mapped[dict] = mapped_column(JSON)
    original_record: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)


class Revision(Base):
    __tablename__ = "extraction_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "extraction_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Cleanup(Base):
    """Durable outbox so a failed vector/file delete can be retried."""

    __tablename__ = "cleanup_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    paper_id: Mapped[str] = mapped_column(String(36), unique=True)
    done: Mapped[bool] = mapped_column(default=False)


class PublicReference(Base):
    __tablename__ = "public_references"
    __table_args__ = (UniqueConstraint("library_id", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JSON)
