from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.sql import func
from app.database import Base

class UserAgreement(Base):
    __tablename__ = 'user_agreements'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BIGINT(unsigned=True), ForeignKey('users.id'), nullable=False)
    terms_version = Column(String(50), nullable=False)
    privacy_version = Column(String(50), nullable=False)
    device_info = Column(Text, nullable=True)
    agreed_at = Column(DateTime(timezone=True), server_default=func.now())
