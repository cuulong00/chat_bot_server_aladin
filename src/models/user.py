from sqlalchemy import Column, Integer, String
from src.models.base import Base

from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.sql import func
from src.models.base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    user_id = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    email = Column(Text)
    phone = Column(Text)
    address = Column(Text)
    citizen_id = Column(Text, unique=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
    # hashed_password = Column(Text, nullable=True)  # Nếu cần auth

