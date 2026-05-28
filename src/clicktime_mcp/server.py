from typing import Optional

from mcp.server.fastmcp import FastMCP

from clicktime_mcp.client import ClickTimeClient, ClickTimeError

mcp = FastMCP(
    "clicktime",
    instructions="Interact with ClickTime: log time, manage timesheets, generate reports.",
)

_client = ClickTimeClient()


def _fmt_error(exc: Exception) -> str:
    if isinstance(exc, ClickTimeError):
        return f"Error: {exc}"
    return f"Unexpected error: {exc}"


# ─── Profile ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_my_profile() -> str:
    """Return the authenticated user's name, email and ID."""
    try:
        result = await _client.get("/Me")
        me = result.get("data", result) if isinstance(result, dict) else result
        # Name is returned as "LastName, FirstName"
        return (
            f"Profile:\n"
            f"  Name:   {me.get('Name')}\n"
            f"  Email:  {me.get('Email')}\n"
            f"  ID:     {me.get('ID')}\n"
            f"  Level:  {me.get('SecurityLevel')}\n"
            f"  Active: {me.get('IsActive')}"
        )
    except Exception as exc:
        return _fmt_error(exc)


# ─── Reference data ───────────────────────────────────────────────────────────

@mcp.tool()
async def list_jobs(active_only: bool = True) -> str:
    """
    List jobs/projects available to the current user.

    Args:
        active_only: Only show active jobs (default true). Set false to include inactive.
    """
    try:
        jobs = await _client.get_all("/Me/Jobs", params={"verbose": "true"})
        if active_only:
            jobs = [j for j in jobs if j.get("IsActive", True)]
        if not jobs:
            return "No jobs found."
        lines = [f"Jobs ({len(jobs)}):\n"]
        for j in jobs:
            client_name = (j.get("Client") or {}).get("Name") or ""
            client_str = f"  [{client_name}]" if client_name else ""
            lines.append(
                f"  [{j.get('ID')}]  #{j.get('JobNumber', '')}  {j.get('Name')}{client_str}"
            )
        return "\n".join(lines)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def list_clients() -> str:
    """List clients available to the current user."""
    try:
        clients = await _client.get_all("/Me/Clients")
        if not clients:
            return "No clients found."
        lines = [f"Clients ({len(clients)}):\n"]
        for c in clients:
            lines.append(f"  [{c.get('ID')}]  {c.get('Name')}")
        return "\n".join(lines)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def list_tasks(active_only: bool = True) -> str:
    """
    List tasks available to the current user.

    Args:
        active_only: Only show active tasks (default true). Set false to include all.
    """
    try:
        tasks = await _client.get_all("/Me/Tasks")
        if active_only:
            tasks = [t for t in tasks if t.get("IsActive", True)]
        if not tasks:
            return "No tasks found."
        lines = [f"Tasks ({len(tasks)}):\n"]
        for t in tasks:
            lines.append(f"  [{t.get('ID')}]  {t.get('Name')}")
        return "\n".join(lines)
    except Exception as exc:
        return _fmt_error(exc)


# ─── Time entries ─────────────────────────────────────────────────────────────

@mcp.tool()
async def list_my_time_entries(
    date_from: str,
    date_to: str,
    job_id: Optional[str] = None,
) -> str:
    """
    List the current user's time entries within a date range.

    Args:
        date_from: Start date (YYYY-MM-DD).
        date_to:   End date (YYYY-MM-DD).
        job_id:    Optional job/project ID filter.
    """
    try:
        from clicktime_mcp.tools.time_entries import list_my_time_entries as _fn
        return await _fn(_client, date_from, date_to, job_id)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def create_time_entry(
    entry_date: str,
    hours: float,
    job_id: str,
    task_id: Optional[str] = None,
    phase_id: Optional[str] = None,
    sub_phase_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """
    Create a new time entry.

    Use list_my_time_entries with verbose=true to see existing Phase/SubPhase IDs for
    a given job, since ClickTime does not expose a dedicated phases endpoint.

    Args:
        entry_date:   Date in YYYY-MM-DD format.
        hours:        Hours worked (e.g. 8.0 or 7.5).
        job_id:       Job/project ID (use list_jobs to find IDs).
        task_id:      Task ID (optional, use list_tasks to find IDs).
        phase_id:     Phase ID (optional — see existing entries for valid IDs).
        sub_phase_id: Sub-phase ID (optional — see existing entries for valid IDs).
        notes:        Description or notes for this entry (optional).
    """
    try:
        from clicktime_mcp.tools.time_entries import create_time_entry as _fn
        return await _fn(_client, entry_date, hours, job_id, task_id, phase_id, sub_phase_id, notes)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def update_time_entry(
    entry_id: str,
    hours: Optional[float] = None,
    job_id: Optional[str] = None,
    task_id: Optional[str] = None,
    phase_id: Optional[str] = None,
    sub_phase_id: Optional[str] = None,
    notes: Optional[str] = None,
    entry_date: Optional[str] = None,
) -> str:
    """
    Update an existing time entry. Only provide the fields you want to change.

    Args:
        entry_id:     ID of the entry to update (use list_my_time_entries to find it).
        hours:        New hours value.
        job_id:       New job ID.
        task_id:      New task ID.
        phase_id:     New phase ID.
        sub_phase_id: New sub-phase ID.
        notes:        New notes/description.
        entry_date:   New date (YYYY-MM-DD).
    """
    try:
        from clicktime_mcp.tools.time_entries import update_time_entry as _fn
        return await _fn(_client, entry_id, hours, job_id, task_id, phase_id, sub_phase_id, notes, entry_date)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def delete_time_entry(entry_id: str) -> str:
    """
    Delete a time entry.

    Args:
        entry_id: ID of the entry to delete.
    """
    try:
        from clicktime_mcp.tools.time_entries import delete_time_entry as _fn
        return await _fn(_client, entry_id)
    except Exception as exc:
        return _fmt_error(exc)


# ─── Timesheets ───────────────────────────────────────────────────────────────

@mcp.tool()
async def list_my_timesheets(status: Optional[str] = None) -> str:
    """
    List your timesheets.

    Args:
        status: Filter by status — 'Open', 'Submitted', or 'Approved' (optional).
    """
    try:
        from clicktime_mcp.tools.timesheets import list_my_timesheets as _fn
        return await _fn(_client, status)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def submit_timesheet(timesheet_id: str) -> str:
    """
    Submit a timesheet for approval.

    Args:
        timesheet_id: ID of the timesheet to submit (use list_my_timesheets to find it).
    """
    try:
        from clicktime_mcp.tools.timesheets import submit_timesheet as _fn
        return await _fn(_client, timesheet_id)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def get_timesheet_status(timesheet_id: str) -> str:
    """
    Show the full status, period, hours, and approval info for a timesheet.

    Args:
        timesheet_id: ID of the timesheet.
    """
    try:
        from clicktime_mcp.tools.timesheets import get_timesheet_status as _fn
        return await _fn(_client, timesheet_id)
    except Exception as exc:
        return _fmt_error(exc)


# ─── Reports ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_weekly_summary() -> str:
    """Show a summary of the current week's time entries grouped by project and day."""
    try:
        from clicktime_mcp.tools.reports import get_weekly_summary as _fn
        return await _fn(_client)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def get_monthly_report(
    year: int,
    month: int,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate a PDF report for a given month and return the file path.

    Args:
        year:        Year (e.g. 2025).
        month:       Month number (1–12).
        output_path: Optional custom path for the PDF file.
                     Defaults to CLICKTIME_REPORT_DIR/clicktime_report_<Month_Year>.pdf
    """
    try:
        from clicktime_mcp.tools.reports import get_monthly_report as _fn
        return await _fn(_client, year, month, output_path)
    except Exception as exc:
        return _fmt_error(exc)


# ─── Manager tools ────────────────────────────────────────────────────────────

@mcp.tool()
async def list_team_members() -> str:
    """List all users accessible to the current manager. Requires manager access."""
    try:
        from clicktime_mcp.tools.manager import list_team_members as _fn
        return await _fn(_client)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def get_member_time_entries(user_id: str, date_from: str, date_to: str) -> str:
    """
    Get time entries for a specific team member. Requires manager access.

    Args:
        user_id:   ID of the team member (use list_team_members to find IDs).
        date_from: Start date (YYYY-MM-DD).
        date_to:   End date (YYYY-MM-DD).
    """
    try:
        from clicktime_mcp.tools.manager import get_member_time_entries as _fn
        return await _fn(_client, user_id, date_from, date_to)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def get_member_timesheets(user_id: str, status: Optional[str] = None) -> str:
    """
    Get timesheets for a specific team member. Requires manager access.

    Args:
        user_id: ID of the team member.
        status:  Optional status filter.
    """
    try:
        from clicktime_mcp.tools.manager import get_member_timesheets as _fn
        return await _fn(_client, user_id, status)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def approve_timesheet(timesheet_id: str, comment: Optional[str] = None) -> str:
    """
    Approve a team member's timesheet. Requires manager access.

    Args:
        timesheet_id: ID of the timesheet to approve.
        comment:      Optional approval comment.
    """
    try:
        from clicktime_mcp.tools.manager import approve_timesheet as _fn
        return await _fn(_client, timesheet_id, comment)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def reject_timesheet(timesheet_id: str, reason: str) -> str:
    """
    Reject a team member's timesheet. Requires manager access.

    Args:
        timesheet_id: ID of the timesheet to reject.
        reason:       Reason for rejection (required).
    """
    try:
        from clicktime_mcp.tools.manager import reject_timesheet as _fn
        return await _fn(_client, timesheet_id, reason)
    except Exception as exc:
        return _fmt_error(exc)


@mcp.tool()
async def get_team_report(year: int, month: int) -> str:
    """
    Show a consolidated hours summary for all team members in a given month.
    Requires manager access.

    Args:
        year:  Year (e.g. 2025).
        month: Month number (1–12).
    """
    try:
        from clicktime_mcp.tools.manager import get_team_report as _fn
        return await _fn(_client, year, month)
    except Exception as exc:
        return _fmt_error(exc)


def main() -> None:
    mcp.run()
