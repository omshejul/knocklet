from collections.abc import Iterable
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from .automation import enqueue_acceptance_check
from .message_templates import validate_rendered_message_body
from .models import ConnectionRequest, Invitation, Message, Person, WorkItem


def available_person_action(
    invitation: Invitation | None,
    message: Message | None,
) -> str | None:
    if invitation is None:
        return "send_request"
    if invitation.status == Invitation.Status.FAILED:
        return "retry_request"
    if invitation.status == Invitation.Status.PENDING:
        return "check_status"
    if message is not None and message.status == Message.Status.FAILED:
        try:
            validate_rendered_message_body(message.body)
        except ValueError:
            return None
        return "retry_message"
    return None


@transaction.atomic
def process_people(person_ids: Iterable[UUID]) -> dict:
    requested_ids = set(person_ids)
    people = list(
        Person.objects.select_for_update()
        .filter(id__in=requested_ids)
        .select_related("invitation", "invitation__message")
    )
    now = timezone.now()
    invitation_count = 0
    message_count = 0
    check_count = 0
    skipped_count = len(requested_ids) - len(people)

    for person in people:
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

        action = available_person_action(invitation, message)
        if action == "send_request":
            invitation = Invitation.objects.create(
                person=person,
                status=Invitation.Status.QUEUED,
                queued_at=now,
            )
            WorkItem.objects.create(
                kind=WorkItem.Kind.SEND_INVITATION,
                invitation=invitation,
                due_at=now,
                dedupe_key=f"invitation:{invitation.id}:{now.isoformat()}",
            )
            invitation_count += 1
            continue

        if action == "retry_request":
            invitation.status = Invitation.Status.QUEUED
            invitation.error = ""
            invitation.provider_status = None
            invitation.queued_at = now
            invitation.sent_at = None
            invitation.accepted_at = None
            invitation.checked_at = None
            invitation.save(
                update_fields=[
                    "status",
                    "error",
                    "provider_status",
                    "queued_at",
                    "sent_at",
                    "accepted_at",
                    "checked_at",
                    "updated_at",
                ]
            )
            invitation.import_rows.update(
                status=ConnectionRequest.Status.READY,
                error="",
                provider_status=None,
                sent_at=None,
                accepted_at=None,
                checked_at=None,
            )
            WorkItem.objects.create(
                kind=WorkItem.Kind.SEND_INVITATION,
                invitation=invitation,
                due_at=now,
                dedupe_key=f"invitation:{invitation.id}:{now.isoformat()}",
            )
            invitation_count += 1
            continue

        if action == "check_status":
            check_count += 1
            continue

        if action == "retry_message" and message is not None:
            message.status = Message.Status.QUEUED
            message.error = ""
            message.provider_status = None
            message.queued_at = now
            message.sent_at = None
            message.save(
                update_fields=[
                    "status",
                    "error",
                    "provider_status",
                    "queued_at",
                    "sent_at",
                    "updated_at",
                ]
            )
            WorkItem.objects.create(
                kind=WorkItem.Kind.SEND_MESSAGE,
                invitation=invitation,
                message=message,
                due_at=now,
                dedupe_key=f"message:{message.id}:{now.isoformat()}",
            )
            message_count += 1
            continue

        skipped_count += 1

    acceptance_work = enqueue_acceptance_check(force=True) if check_count else None
    return {
        "requested_count": len(requested_ids),
        "invitation_count": invitation_count,
        "message_count": message_count,
        "check_count": check_count,
        "skipped_count": skipped_count,
        "acceptance_work_item_id": str(acceptance_work.id) if acceptance_work else None,
    }
