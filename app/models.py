# app/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import Config

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    uploads = relationship("Upload", back_populates="owner")

class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True)
    cid = Column(String(255), nullable=False, index=True)
    filename = Column(String(255))
    content_type = Column(String(120))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="uploads")
    pinata_response = Column(Text)

# Database setup
engine = create_engine(Config.DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def db_session():
    """Return a new DB session. Use this from other modules and remember to close it."""
    return SessionLocal()

def init_db():
    """Create tables (call at app startup)."""
    Base.metadata.create_all(engine)
