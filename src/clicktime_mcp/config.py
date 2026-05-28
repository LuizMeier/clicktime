import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN: str = os.environ.get("CLICKTIME_API_TOKEN", "")
API_BASE_URL: str = "https://api.clicktime.com/v2"
REPORT_OUTPUT_DIR: str = os.environ.get("CLICKTIME_REPORT_DIR", ".")

if not API_TOKEN:
    raise EnvironmentError(
        "CLICKTIME_API_TOKEN is not set. "
        "Add it to your .env file or MCP server environment config."
    )
