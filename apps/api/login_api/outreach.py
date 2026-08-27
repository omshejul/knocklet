from django.db.models import Case, F, Max, OuterRef, Subquery, When

from .message_templates import render_template_body
from .models import (
    ConnectionImport,
    Invitation,
    Message,
    MessageTemplate,
    Person,
    WorkItem,
)


def list_people(limit: int = 500) -> list[dict]:
    automatic_message_template = (
        ConnectionImport.objects.filter(
            requests__invitation__person_id=OuterRef("pk"),
            auto_message_enabled=True,
            message_template__isnull=False,
        )
        .annotate(
            resolved_body=Case(
                When(message_template_body="", then=F("message_template__body")),
                default=F("message_template_body"),
            )
        )
        .order_by("-created_at")
    )
    people = (
        Person.objects.select_related("invitation", "invitation__message")
        .annotate(
            last_imported_at=Max("import_rows__connection_import__created_at"),
            automatic_message_template_body=Subquery(
                automatic_message_template.values("resolved_body")[:1]
            ),
            active_message_template_body=Subquery(
                MessageTemplate.objects.filter(is_active=True).values("body")[:1]
            ),
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

    message_body = message.body if message else None
    if invitation is not None and message_body is None:
        template_body = (
            person.automatic_message_template_body
            or person.active_message_template_body
        )
        if template_body:
            message_body = render_template_body(template_body, person.name)

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
        "message_body": message_body,
        "message_due_at": (
            person.message_due_at.isoformat() if person.message_due_at else None
        ),
        "message_sent_at": message.sent_at.isoformat() if message and message.sent_at else None,
        "last_activity_at": last_activity.isoformat(),
    }
