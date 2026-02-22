import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from app.database import Base, engine
from app.models.compliance import UserAgreement

print("Creating user_agreements table...")
Base.metadata.create_all(bind=engine, tables=[UserAgreement.__table__])
print("Done!")
