from typing import Optional

from clicktime_mcp.client import ClickTimeClient


def _ts_line(ts: dict) -> str:
    submitted = ts.get("SubmittedDate") or ("yes" if ts.get("HasBeenSubmitted") else "no")
    hours = sum(d.get("Hours", 0) for d in ts.get("DayTotals", []))
    actions = [a.get("Action") for a in ts.get("Actions", []) if a.get("Action")]
    actions_str = f"  [can: {', '.join(actions)}]" if actions else ""
    return (
        f"  [{ts.get('ID')}]  {ts.get('StartDate')} → {ts.get('EndDate')}"
        f"  |  {hours:.2f}h"
        f"  |  Status: {ts.get('Status')}"
        f"  |  Submitted: {submitted}"
        f"{actions_str}"
    )


async def list_my_timesheets(client: ClickTimeClient, status: Optional[str] = None) -> str:
    params: dict = {"verbose": "true"}
    if status:
        params["status"] = status

    timesheets = await client.get_all("/Me/Timesheets", params=params)

    if not timesheets:
        return "No timesheets found."

    lines = [f"Your timesheets ({len(timesheets)} total):\n"]
    for ts in sorted(timesheets, key=lambda x: x.get("StartDate", ""), reverse=True):
        lines.append(_ts_line(ts))
    return "\n".join(lines)


async def submit_timesheet(client: ClickTimeClient, timesheet_id: str) -> str:
    await client.post(f"/Me/Timesheets/{timesheet_id}/Actions", {"Action": "Submit"})
    return f"Timesheet {timesheet_id} submitted for approval."


async def get_timesheet_status(client: ClickTimeClient, timesheet_id: str) -> str:
    result = await client.get(f"/Me/Timesheets/{timesheet_id}", params={"verbose": "true"})
    ts = result.get("data", result) if isinstance(result, dict) else result

    hours = sum(d.get("Hours", 0) for d in ts.get("DayTotals", []))
    actions = [a.get("Action") for a in ts.get("Actions", []) if a.get("Action")]

    return (
        f"Timesheet {timesheet_id}:\n"
        f"  Period:      {ts.get('StartDate')} → {ts.get('EndDate')}\n"
        f"  Status:      {ts.get('Status')}\n"
        f"  Hours:       {hours:.2f}h\n"
        f"  Submitted:   {ts.get('SubmittedDate') or ('Yes' if ts.get('HasBeenSubmitted') else 'Not yet')}\n"
        f"  Approved by: {(ts.get('ApprovedBy') or {}).get('Name') or 'N/A'}\n"
        f"  Approved on: {ts.get('ApprovedDate') or 'N/A'}\n"
        f"  Available actions: {', '.join(actions) if actions else 'none'}"
    )
