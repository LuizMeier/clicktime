import calendar
from typing import Optional

from clicktime_mcp.client import ClickTimeClient


async def list_team_members(client: ClickTimeClient) -> str:
    users = await client.get_all("/Users")
    if not users:
        return "No team members found — this endpoint requires manager or admin access."

    lines = [f"Team members ({len(users)} total):\n"]
    for u in users:
        name = f"{u.get('FirstName', '')} {u.get('LastName', '')}".strip()
        lines.append(f"  [{u.get('ID')}]  {name}  <{u.get('Email', '')}>")
    return "\n".join(lines)


async def get_member_time_entries(
    client: ClickTimeClient,
    user_id: str,
    date_from: str,
    date_to: str,
) -> str:
    params = {"startDate": date_from, "endDate": date_to, "verbose": "true"}
    entries = await client.get_all(f"/Users/{user_id}/TimeEntries", params=params)

    if not entries:
        return f"No entries for user {user_id} between {date_from} and {date_to}."

    total = sum(float(e.get("Hours", 0)) for e in entries)
    lines = [f"Time entries for user {user_id} ({date_from} → {date_to}):\n"]
    for e in entries:
        hours = float(e.get("Hours", 0))
        job = e.get("JobName") or e.get("JobID") or "—"
        lines.append(f"  {e.get('Date')}  {hours:.2f}h  {job}  {e.get('Comment', '')}")

    lines.append(f"\nTotal: {total:.2f}h")
    return "\n".join(lines)


async def get_member_timesheets(
    client: ClickTimeClient,
    user_id: str,
    status: Optional[str] = None,
) -> str:
    params: dict = {"verbose": "true"}
    if status:
        params["status"] = status

    timesheets = await client.get_all(f"/Users/{user_id}/Timesheets", params=params)
    if not timesheets:
        return f"No timesheets found for user {user_id}."

    lines = [f"Timesheets for user {user_id}:\n"]
    for ts in timesheets:
        lines.append(
            f"  [{ts.get('ID')}]  {ts.get('StartDate')} → {ts.get('EndDate')}"
            f"  |  {float(ts.get('TotalHours', 0)):.2f}h"
            f"  |  {ts.get('Status')}"
        )
    return "\n".join(lines)


async def approve_timesheet(
    client: ClickTimeClient,
    timesheet_id: str,
    comment: Optional[str] = None,
) -> str:
    payload: dict = {"Action": "approve"}
    if comment:
        payload["Comment"] = comment
    await client.post(f"/Timesheets/{timesheet_id}/Actions", payload)
    return f"Timesheet {timesheet_id} approved."


async def reject_timesheet(client: ClickTimeClient, timesheet_id: str, reason: str) -> str:
    await client.post(
        f"/Timesheets/{timesheet_id}/Actions",
        {"Action": "reject", "Comment": reason},
    )
    return f"Timesheet {timesheet_id} rejected. Reason: {reason}"


async def get_team_report(client: ClickTimeClient, year: int, month: int) -> str:
    last_day = calendar.monthrange(year, month)[1]
    date_from = f"{year}-{month:02d}-01"
    date_to = f"{year}-{month:02d}-{last_day:02d}"

    users = await client.get_all("/Users")
    if not users:
        return "No team members found or insufficient permissions."

    lines = [f"Team report — {year}-{month:02d}:\n"]
    grand_total = 0.0

    for u in users:
        uid = u.get("ID")
        name = f"{u.get('FirstName', '')} {u.get('LastName', '')}".strip()
        entries = await client.get_all(
            f"/Users/{uid}/TimeEntries",
            params={"startDate": date_from, "endDate": date_to},
        )
        hours = sum(float(e.get("Hours", 0)) for e in entries)
        grand_total += hours
        lines.append(f"  {name:<30}  {hours:.2f}h")

    lines.append(f"\nGrand total: {grand_total:.2f}h across {len(users)} members")
    return "\n".join(lines)
