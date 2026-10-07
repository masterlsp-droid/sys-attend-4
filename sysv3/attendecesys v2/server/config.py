import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")
DEVICE_KEY = os.getenv("DEVICE_KEY", "default-dev-key")
PORT = int(os.getenv("PORT", 8000))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.5))
