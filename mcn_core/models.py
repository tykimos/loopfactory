"""SQLAlchemy ORM models for LoopFactory."""
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    display_name = Column(String)
    bio = Column(Text)
    status = Column(String, default="DESIGN")
    activation_url = Column(String)
    activation_code = Column(String)
    ghost_md = Column(Text)
    shell_md = Column(Text)
    is_protected = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    registered_at = Column(DateTime)
    activated_at = Column(DateTime)
    retired_at = Column(DateTime)
    last_heartbeat = Column(DateTime)

class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id"))
    recorded_at = Column(DateTime, server_default=func.now())
    total_bucks = Column(Integer)
    follower_count = Column(Integer)
    following_count = Column(Integer)
    post_count = Column(Integer)
    comment_count = Column(Integer)
    upvote_count = Column(Integer)

class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id"))
    activity_type = Column(String)
    details = Column(Text)
    success = Column(Boolean)
    created_at = Column(DateTime, server_default=func.now())

class PendingActivation(Base):
    __tablename__ = "pending_activation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id"))
    activation_url = Column(String, nullable=False)
    activation_code = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    last_checked = Column(DateTime)
    check_count = Column(Integer, default=0)
