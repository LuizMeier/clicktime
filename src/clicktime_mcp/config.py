import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root regardless of the working directory
# when the MCP server is launched.
# Path: config.py → clicktime_mcp/ → src/ → project_root/
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

API_TOKEN: str = os.environ.get("CLICKTIME_API_TOKEN", "")
API_BASE_URL: str = "https://api.clicktime.com/v2"
REPORT_OUTPUT_DIR: str = os.environ.get("CLICKTIME_REPORT_DIR", ".")

if not API_TOKEN:
    raise EnvironmentError(
        f"CLICKTIME_API_TOKEN is not set. Add it to {_ENV_PATH}"
    )
