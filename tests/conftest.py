import os

# Config reads these at import time. Dummy values: the unit tests never touch a real database or model.
os.environ.setdefault("DATABASE_URL", "postgresql://app:app@localhost:5432/knowledge")
os.environ.setdefault("JWT_SECRET", "x" * 40)
