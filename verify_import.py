import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from app.models.models import Users
    from app.database import get_db
    print("Imports successful")
except Exception as e:
    print(f"Import failed: {e}")
