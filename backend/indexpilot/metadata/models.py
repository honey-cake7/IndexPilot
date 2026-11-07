import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MonitoredDatabase(Base):
    __tablename__ = "monitored_database"
    __table_args__ = (CheckConstraint("port BETWEEN 1 AND 65535", name="valid_port"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    target_key: Mapped[str] = mapped_column(String(80), unique=True)
    host: Mapped[str] = mapped_column(String(253))
    port: Mapped[int] = mapped_column(Integer)
    database_name: Mapped[str] = mapped_column(String(63))
    role_name: Mapped[str] = mapped_column(String(63))
    credential_reference: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
