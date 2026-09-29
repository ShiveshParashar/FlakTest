from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

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