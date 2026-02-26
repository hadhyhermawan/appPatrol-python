import sys
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Karyawan
from sqlalchemy import inspection

db = SessionLocal()
model = Karyawan
mapper = inspection.inspect(model)
for column in mapper.columns:
    print(column.name)
