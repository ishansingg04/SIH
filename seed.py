import os
import sys

# Ensure apps/api is on the python search path
sys.path.insert(0, os.path.abspath("apps/api"))

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db.seed import seed_database

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        result = seed_database(session)
        print("\n" + "=" * 60)
        print("DATABASE INITIALIZED AND SEEDED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Clinic: {result.get('clinic_code')}")
        print(f"Demo Patient: {result.get('demo_patient')}")
        print(f"Demo Token: {result.get('demo_token')}")
        print(f"Users Seeded: {', '.join(result.get('users_seeded', []))}")
        print("=" * 60 + "\n")
