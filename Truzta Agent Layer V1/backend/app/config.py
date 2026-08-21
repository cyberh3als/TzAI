from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CLIENT_MEMORY_DIR = DATA_DIR / "client-memory"
SCF_PATH = DATA_DIR / "catalog" / "scf_controls.json"

load_dotenv(BACKEND_DIR / ".env")
