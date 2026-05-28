from typing import Optional

from clicktime_mcp.client import ClickTimeClient


def _entry_line(e: dict) -> str:
    """Format a single time entry as a readable line."""
    hours = float(e.get("Hours", 0))
    job = (e.get("Job") or {}).get("Name") or e.get("JobID") or "—"
    task = (e.get("Task") or {}).get("Name") or e.get("TaskID") or ""
    phase = (e.get("Phase") or {}).get("Name") or ""
    subphase = (e.get("SubPhase") or {}).get("Name") or ""
    notes = e.get("Comment") or ""

    hierarchy = " › ".join(filter(None, [job, phase, subphase, task]))
    return (
        f"  [{e.get('ID')}] {e.get('Date')}  {hours:.2f}h  {hierarchy}"
        + (f"  ↳ {notes}" if notes else "")
    )


async def list_my_time_entries(
    client: ClickTimeClient,
    date_from: str,
    date_to: str,
    job_id: Optional[str] = None,
) -> str:
    params: dict = {"startDate": date_from, "endDate": date_to, "verbose": "true"}
    if job_id:
        params["jobID"] = job_id

    entries = await client.get_all("/Me/TimeEntries", params=params)

    if not entries:
        return f"No time entries found between {date_from} and {date_to}."

    total_hours = sum(float(e.get("Hours", 0)) for e in entries)
    lines = [f"Time entries from {date_from} to {date_to}:\n"]
    for e in entries:
        lines.append(_entry_line(e))

    lines.append(f"\nTotal: {total_hours:.2f}h  ({len(entries)} entries)")
    return "\n".join(lines)


async def create_time_entry(
    client: ClickTimeClient,
    entry_date: str,
    hours: float,
    job_id: str,
    task_id: Optional[str] = None,
    phase_id: Optional[str] = None,
    sub_phase_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    payload: dict = {"Date": entry_date, "Hours": hours, "JobID": job_id}
    if task_id:
        payload["TaskID"] = task_id
    if phase_id:
        payload["PhaseID"] = phase_id
    if sub_phase_id:
        payload["SubPhaseID"] = sub_phase_id
    if notes:
        payload["Comment"] = notes

    result = await client.post("/Me/TimeEntries", payload)
    # ClickTime returns the created entry under 'data'
    created = result.get("data", result) if isinstance(result, dict) else result
    entry_id = created.get("ID", "?") if isinstance(created, dict) else "?"
    return f"Created: [{entry_id}] {entry_date} — {hours}h on job {job_id}"


async def update_time_entry(
    client: ClickTimeClient,
    entry_id: str,
    hours: Optional[float] = None,
    job_id: Optional[str] = None,
    task_id: Optional[str] = None,
    phase_id: Optional[str] = None,
    sub_phase_id: Optional[str] = None,
    notes: Optional[str] = None,
    entry_date: Optional[str] = None,
) -> str:
    payload: dict = {}
    if hours is not None:
        payload["Hours"] = hours
    if job_id:
        payload["JobID"] = job_id
    if task_id:
        payload["TaskID"] = task_id
    if phase_id:
        payload["PhaseID"] = phase_id
    if sub_phase_id:
        payload["SubPhaseID"] = sub_phase_id
    if notes is not None:
        payload["Comment"] = notes
    if entry_date:
        payload["Date"] = entry_date

    if not payload:
        return "Nothing to update — no fields provided."

    await client.put(f"/Me/TimeEntries/{entry_id}", payload)
    changed = ", ".join(f"{k}={v}" for k, v in payload.items())
    return f"Entry {entry_id} updated: {changed}"


async def delete_time_entry(client: ClickTimeClient, entry_id: str) -> str:
    await client.delete(f"/Me/TimeEntries/{entry_id}")
    return f"Entry {entry_id} deleted."
