from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32))
    team: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    service: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    failure: Mapped[str] = mapped_column(String(255))
    root_cause: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    severity: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    date: Mapped[str] = mapped_column(String(32))
    resolved_by: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[str] = mapped_column(Text)


class Solution(Base):
    __tablename__ = "solutions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    message: Mapped[str] = mapped_column(Text)
    node: Mapped[str] = mapped_column(String(64), default="")


class HarnessRun(Base):
    __tablename__ = "harness_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(64))
    incident_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running")
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


connect_args = {"check_same_thread": False, "timeout": 15} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
