from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    repository: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    commit_sha: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    total_tests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    passed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    skipped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # One TestRun can contain many TestResults
    test_results: Mapped[list["TestResult"]] = relationship(
        back_populates="test_run",
        cascade="all, delete-orphan",
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id"),
        nullable=False,
        index=True,
    )

    test_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    outcome: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    duration: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    test_run: Mapped["TestRun"] = relationship(
        back_populates="test_results",
    )