from django.db.models import Q
from django.db.models.functions import Coalesce

from .models import WorkItem


def list_logs(
    *,
    limit: int = 50,
    offset: int = 0,
    search: str = "",
    status: str = "",
    kind: str = "",
) -> dict:
    work_items = (
        WorkItem.objects.select_related(
            "invitation__person",
            "message__invitation__person",
        )
        .annotate(activity_at=Coalesce("completed_at", "started_at", "created_at"))
        .order_by("-activity_at", "-created_at")
    )
    cleaned_search = search.strip()
    if cleaned_search:
        work_items = work_items.filter(
            Q(invitation__person__name__icontains=cleaned_search)
            | Q(message__invitation__person__name__icontains=cleaned_search)
        )
    if status:
        work_items = work_items.filter(status=status)
    if kind:
        work_items = work_items.filter(kind=kind)

    page = list(work_items[offset : offset + limit + 1])
    has_more = len(page) > limit
    items = page[:limit]
    return {
        "items": [_log_snapshot(work_item) for work_item in items],
        "has_more": has_more,
        "next_offset": offset + len(items) if has_more else None,
    }


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
        "activity_at": work_item.activity_at.isoformat(),
        "due_at": work_item.due_at.isoformat(),
        "created_at": work_item.created_at.isoformat(),
        "started_at": (
            work_item.started_at.isoformat() if work_item.started_at else None
        ),
        "completed_at": (
            work_item.completed_at.isoformat() if work_item.completed_at else None
        ),
    }
