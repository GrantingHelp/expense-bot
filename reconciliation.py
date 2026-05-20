from trip_log import (
    get_current_trip, get_trip_summary, get_unassigned_receipts,
    get_assigned_receipts, update_receipt_sites, load_log
)
from datetime import datetime


def format_receipt_line(receipt: dict, index: int = None) -> str:
    vendor = receipt.get("VENDOR", "Unknown")
    category = receipt.get("CATEGORY", "Unknown")
    date = receipt.get("DATE", "Unknown")
    amount = receipt.get("AMOUNT", "Unknown")
    sites = receipt.get("SITES", [])

    prefix = f"{index}. " if index else "• "
    site_str = ", ".join(sites) if sites else "{SITE ID NEEDED}"

    return (
        f"{prefix}{vendor} — {category} — ${amount} — {date}\n"
        f"   📍 {site_str}"
    )


def format_trip_summary(trip: dict) -> str:
    name = trip.get("name", "Unknown Trip")
    started = trip.get("started", "")
    receipts = sorted(
        trip.get("receipts", []),
        key=lambda r: r.get("logged_at", "")
    )

    try:
        date_str = datetime.fromisoformat(started).strftime("%b %d, %Y")
    except Exception:
        date_str = "Unknown date"

    lines = [
        f"📋 Trip: {name}",
        f"📅 {date_str}",
        f"🧾 {len(receipts)} receipt{'s' if len(receipts) != 1 else ''}",
        ""
    ]

    for i, receipt in enumerate(receipts, 1):
        lines.append(format_receipt_line(receipt, i))
        lines.append("")

    return "\n".join(lines).strip()


def start_reconciliation(trip_id: str) -> tuple[list, str]:
    unassigned = get_unassigned_receipts(trip_id)

    if not unassigned:
        return [], "✅ All receipts are already assigned. Say 'review assigned' to update any of them."

    first = unassigned[0]
    msg = (
        f"Let's sort your unassigned receipts. "
        f"You have {len(unassigned)} to go through.\n\n"
        f"{format_receipt_line(first)}\n\n"
        f"Which site(s) is this for? You can reply with:\n"
        f"• A site code e.g. L-1100333\n"
        f"• A description e.g. 'first stop'\n"
        f"• Multiple sites separated by commas\n"
        f"• 'skip' to leave it unassigned for now"
    )

    return unassigned, msg


def start_review_assigned(trip_id: str) -> tuple[list, str]:
    assigned = get_assigned_receipts(trip_id)

    if not assigned:
        return [], "No assigned receipts to review yet."

    first = assigned[0]
    msg = (
        f"Reviewing assigned receipts. "
        f"You have {len(assigned)} to go through.\n\n"
        f"{format_receipt_line(first)}\n\n"
        f"Reply with new site(s), or say 'keep' to leave it as is."
    )

    return assigned, msg


def build_next_prompt(receipt: dict, remaining: int, mode: str = "reconcile") -> str:
    action = "keep" if mode == "review" else "skip"
    return (
        f"{format_receipt_line(receipt)}\n\n"
        f"Which site(s) is this for? "
        f"({remaining} remaining — say '{action}' to leave as is)"
    )