from django.db.models import Max, OuterRef, Subquery

from .models import Invitation, Message, Person, WorkItem


def list_people(limit: int = 500) -> list[dict]:
    people = (
        Person.objects.select_related("invitation", "invitation__message")
        .annotate(
            last_imported_at=Max("import_rows__connection_import__created_at"),
            message_due_at=Subquery(
                WorkItem.objects.filter(
                    kind=WorkItem.Kind.SEND_MESSAGE,
                    message__invitation__person_id=OuterRef("pk"),
                )
                .order_by("-created_at")
                .values("due_at")[:1]
            ),
        )
        .order_by("-invitation__updated_at", "-last_imported_at", "name")[:limit]
    )
    return [_person_snapshot(person) for person in people]


def _person_snapshot(person: Person) -> dict:
    try:
        invitation = person.invitation
    except Invitation.DoesNotExist:
        invitation = None

    message = None
    if invitation is not None:
        try:
            message = invitation.message
        except Message.DoesNotExist:
            message = None

    activity_dates = [person.updated_at, person.last_imported_at]
    if invitation:
        activity_dates.extend(
            [invitation.updated_at, invitation.checked_at, invitation.accepted_at]
        )
    if message:
        activity_dates.extend([message.updated_at, message.sent_at])
    last_activity = max(value for value in activity_dates if value is not None)

    return {
        "id": str(person.id),
        "name": person.name,
        "linkedin_url": person.linkedin_url,
        "public_id": person.public_id,
        "invitation_status": invitation.status if invitation else "not_started",
        "invitation_error": invitation.error or None if invitation else None,
        "invitation_provider_status": invitation.provider_status if invitation else None,
        "sent_at": invitation.sent_at.isoformat() if invitation and invitation.sent_at else None,
        "accepted_at": (
            invitation.accepted_at.isoformat()
            if invitation and invitation.accepted_at
            else None
        ),
        "checked_at": invitation.checked_at.isoformat() if invitation and invitation.checked_at else None,
        "message_status": message.status if message else "not_scheduled",
        "message_error": message.error or None if message else None,
        "message_body": message.body if message else None,
        "message_due_at": (
            person.message_due_at.isoformat() if person.message_due_at else None
        ),
        "message_sent_at": message.sent_at.isoformat() if message and message.sent_at else None,
        "last_activity_at": last_activity.isoformat(),
    }
