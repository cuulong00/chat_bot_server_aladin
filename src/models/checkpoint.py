from sqlalchemy import Column, String, Integer, Text, LargeBinary, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.models.base import Base

class Checkpoint(Base):
    __tablename__ = "checkpoints"
    thread_id = Column(Text, primary_key=True)
    checkpoint_ns = Column(Text, primary_key=True, default="")
    checkpoint_id = Column(Text, primary_key=True)
    parent_checkpoint_id = Column(Text, nullable=True)
    type = Column(Text)
    checkpoint = Column(JSONB, nullable=False)
    metadata_ = Column('metadata', JSONB, nullable=False, default=dict)
    created_at = Column(Text)  

class CheckpointWrite(Base):
    __tablename__ = "checkpoint_writes"
    thread_id = Column(Text, primary_key=True)
    checkpoint_ns = Column(Text, primary_key=True, default="")
    checkpoint_id = Column(Text, primary_key=True)
    task_id = Column(Text, primary_key=True)
    idx = Column(Integer, primary_key=True)
    channel = Column(Text, nullable=False)
    type = Column(Text)
    blob = Column(LargeBinary, nullable=False)
    task_path = Column(Text, nullable=False, default="")

class CheckpointBlob(Base):
    __tablename__ = "checkpoint_blobs"
    thread_id = Column(Text, primary_key=True)
    checkpoint_ns = Column(Text, primary_key=True, default="")
    channel = Column(Text, primary_key=True)
    version = Column(Text, primary_key=True)
    type = Column(Text, primary_key=True)
    blob = Column(LargeBinary)
