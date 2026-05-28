# ClickTime MCP Server

An MCP (Model Context Protocol) server that lets you manage ClickTime time tracking through natural language in Claude Code. Log hours, submit timesheets, generate PDF reports, and — for managers — review and approve your team's time.

---

## How it works

```
You (natural language)
      ↓
Claude Code
      ↓  calls tools
ClickTime MCP Server  (runs locally)
      ↓  HTTPS + token
ClickTime API
```

The server runs as a local process. Your API token lives in an environment variable and never appears in the conversation.

---

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- A ClickTime account on the **Team plan or higher**
- A ClickTime API token (see below)

---

## Getting your API token

1. Log into ClickTime
2. Go to **My Preferences → Authentication Token**
3. Copy the token

---

## Installation

```bash
# Clone the repo
git clone <repo-url>
cd clicktime-mcp

# Install dependencies
uv sync

# Configure your token
cp .env.example .env
# Edit .env and paste your token into CLICKTIME_API_TOKEN
```

---

## Configuration

`.env` (never commit this file):

```env
CLICKTIME_API_TOKEN=your_token_here
CLICKTIME_REPORT_DIR=./reports   # where PDFs are saved
```

---

## Adding to Claude Code

Edit (or create) `.claude/settings.json` in your project, or the global settings at `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "clicktime": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/to/clicktime-mcp",
        "run", "clicktime-mcp"
      ],
      "env": {
        "CLICKTIME_REPORT_DIR": "/absolute/path/to/reports"
      }
    }
  }
}
```

> The API token is read directly from the `.env` file at the project root — no need to add it to the MCP `env` block. The server resolves the `.env` path relative to the package location, so it works regardless of the working directory Claude Code is launched from.

After saving, restart Claude Code. You should see `clicktime` listed as a connected MCP server.

---

## Available tools

### Profile
| Tool | Description |
|---|---|
| `get_my_profile` | Your name, email and user ID |

### Reference data
| Tool | Description |
|---|---|
| `list_jobs` | All projects/jobs available to you |
| `list_tasks` | All tasks, optionally filtered by job |

### Time entries
| Tool | Description |
|---|---|
| `list_my_time_entries` | Entries in a date range |
| `create_time_entry` | Log hours for a date |
| `update_time_entry` | Edit an existing entry |
| `delete_time_entry` | Remove an entry |

### Timesheets
| Tool | Description |
|---|---|
| `list_my_timesheets` | Your timesheets, optionally filtered by status |
| `submit_timesheet` | Submit for approval |
| `get_timesheet_status` | Full status and approval info |

### Reports
| Tool | Description |
|---|---|
| `get_weekly_summary` | Current week totals by project and day |
| `get_monthly_report` | Generate a PDF report for a given month |

### Manager tools
> These require manager or admin permissions in ClickTime.

| Tool | Description |
|---|---|
| `list_team_members` | All users you can manage |
| `get_member_time_entries` | A team member's entries in a date range |
| `get_member_timesheets` | A team member's timesheets |
| `approve_timesheet` | Approve a timesheet |
| `reject_timesheet` | Reject a timesheet with a reason |
| `get_team_report` | Consolidated hours for the whole team in a month |

---

## Usage examples

### Log a full work week

> "Log 8 hours per day Monday through Friday this week on the XPTO project with note 'backend development'."

Claude will call `list_jobs` to find the job ID, then `create_time_entry` five times.

---

### Submit your timesheet

> "Submit my timesheet for this week."

Claude calls `list_my_timesheets` to find the open timesheet, then `submit_timesheet`.

---

### Generate a monthly PDF report

> "Generate the April 2025 report as a PDF."

Claude calls `get_monthly_report(year=2025, month=4)`. The PDF is saved to `CLICKTIME_REPORT_DIR` and the path is returned.

The PDF is formatted as a **Vertical Timesheet** (portrait A4), matching the ClickTime web export:
- One section per calendar day (including weekends with 0.00 Total)
- Entry rows with project, task, and comment columns
- Bold daily total per day
- Grand Total row on the last page
- Per-page footer with signature lines and "Prepared by ClickTime on \<date\> — Page X of Y"

---

### Manager: review pending timesheets

> "Show me all submitted timesheets from my team this week."

Claude calls `list_team_members`, then `get_member_timesheets` for each member filtered by `Submitted`.

> "Approve João's timesheet."

Claude calls `approve_timesheet` with the correct ID.

---

### Weekly check-in

> "How many hours have I logged this week?"

Claude calls `get_weekly_summary` and shows the breakdown.

---

## Troubleshooting

**`CLICKTIME_API_TOKEN is not set`**
Make sure the token is in the `env` block of your MCP config (or in `.env` if running locally).

**`Error: ClickTime API error 401`**
The token is invalid or expired. Generate a new one in ClickTime → My Preferences → Authentication Token.

**`Error: ClickTime API error 403`**
You don't have permission for that action (e.g. manager tools for a regular user account).

**`Error: ClickTime API error 429`**
Rate limit hit. Wait a few seconds. The `/TimeEntries` endpoint allows 10 requests per 5 seconds.

**PDF not generated**
Make sure `CLICKTIME_REPORT_DIR` points to a directory you have write access to.

---

## Future automation

The MCP server can be called from scripts without Claude:

```python
import asyncio
from clicktime_mcp.client import ClickTimeClient
from clicktime_mcp.tools.reports import get_monthly_report

async def run():
    client = ClickTimeClient()
    result = await get_monthly_report(client, year=2025, month=4)
    print(result)

asyncio.run(run())
```

You can also use Claude Code's `/schedule` feature to set up recurring reminders — for example, every Friday to submit your timesheet.
