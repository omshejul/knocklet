from .models import WorkItem


def list_logs(limit: int = 500) -> list[dict]:
    work_items = (
        WorkItem.objects.select_related(
            "invitation__person",
            "message__invitation__person",
        )
        .order_by("-created_at")[:limit]
    )
    return [_log_snapshot(work_item) for work_item in work_items]


def _log_snapshot(work_item: WorkItem) -> dict:
    invitation = work_item.invitation
    if invitation is None and work_item.message is not None:
        invitation = work_item.message.invitation
    person = invitation.person if invitation else None
    return {
        "id": str(work_item.id),
        "kind": work_item.kind,
        "status": work_item.status,
        "person_name": person.name if person else None,
        "error": work_item.error or None,
        "provider_status": work_item.provider_status,
        "attempt_count": work_item.attempt_count,
        "due_at": work_item.due_at.isoformat(),
        "created_at": work_item.created_at.isoformat(),
        "started_at": (
            work_item.started_at.isoformat() if work_item.started_at else None
        ),
        "completed_at": (
            work_item.completed_at.isoformat() if work_item.completed_at else None
        ),
    }
