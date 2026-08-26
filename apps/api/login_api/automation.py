from collections.abc import Callable
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone

from django.db import transaction
from django.utils import timezone

from .models import (
    ConnectionImport,
    ConnectionRequest,
    Invitation,
    Message,
    MessageTemplate,
    Person,
    WorkItem,
)

ClientFactory = Callable[[], object]
ACCEPTANCE_INTERVAL = timedelta(minutes=30)


def default_client_factory():
    from auth import get_client

    return get_client()


def queue_invitation(connection_request: ConnectionRequest) -> Invitation:
    person, _ = Person.objects.update_or_create(
        normalized_public_id=connection_request.public_id.strip().casefold(),
        defaults={
            "name": connection_request.name,
            "linkedin_url": connection_request.linkedin_url,
            "public_id": connection_request.public_id,
        },
    )
    invitation, created = Invitation.objects.get_or_create(
        person=person,
        defaults={
            "status": Invitation.Status.QUEUED,
            "queued_at": timezone.now(),
        },
    )
    if not created and invitation.status not in {
        Invitation.Status.FAILED,
        Invitation.Status.CANCELLED,
    }:
        connection_request.person = person
        connection_request.invitation = invitation
        connection_request.save(update_fields=["person", "invitation"])
        return invitation

    if not created:
        invitation.status = Invitation.Status.QUEUED
        invitation.error = ""
        invitation.provider_status = None
        invitation.queued_at = timezone.now()
        invitation.save(
            update_fields=[
                "status",
                "error",
                "provider_status",
                "queued_at",
                "updated_at",
            ]
        )

    connection_request.person = person
    connection_request.invitation = invitation
    connection_request.save(update_fields=["person", "invitation"])
    WorkItem.objects.get_or_create(
        dedupe_key=f"invitation:{invitation.id}:{invitation.queued_at.isoformat()}",
        defaults={
            "kind": WorkItem.Kind.SEND_INVITATION,
            "invitation": invitation,
            "due_at": timezone.now(),
        },
    )
    return invitation


def enqueue_acceptance_check(*, force: bool = False) -> WorkItem | None:
    if not Invitation.objects.filter(status=Invitation.Status.PENDING).exists():
        return None

    active = WorkItem.objects.filter(
        kind=WorkItem.Kind.CHECK_ACCEPTANCES,
        status__in=[WorkItem.Status.QUEUED, WorkItem.Status.RUNNING],
    ).order_by("due_at").first()
    now = timezone.now()
    if active:
        if force and active.status == WorkItem.Status.QUEUED and active.due_at > now:
            active.due_at = now
            active.save(update_fields=["due_at"])
        return active

    last_check = WorkItem.objects.filter(
        kind=WorkItem.Kind.CHECK_ACCEPTANCES,
        status=WorkItem.Status.SUCCEEDED,
        completed_at__isnull=False,
    ).order_by("-completed_at").first()
    due_at = now if force or last_check is None else last_check.completed_at + ACCEPTANCE_INTERVAL
    return WorkItem.objects.create(
        kind=WorkItem.Kind.CHECK_ACCEPTANCES,
        due_at=due_at,
        dedupe_key=f"acceptance:{due_at.isoformat()}",
    )


def run_due_work_once(client_factory: ClientFactory | None = None) -> WorkItem | None:
    with transaction.atomic():
        work_item = (
            WorkItem.objects.select_for_update()
            .filter(status=WorkItem.Status.QUEUED, due_at__lte=timezone.now())
            .order_by("due_at", "created_at")
            .first()
        )
        if work_item is None:
            return None
        work_item.status = WorkItem.Status.RUNNING
        work_item.started_at = timezone.now()
        work_item.attempt_count += 1
        work_item.save(update_fields=["status", "started_at", "attempt_count"])

    factory = client_factory or default_client_factory
    try:
        client = factory()
        if work_item.kind == WorkItem.Kind.SEND_INVITATION:
            _send_invitation(work_item, client)
        elif work_item.kind == WorkItem.Kind.CHECK_ACCEPTANCES:
            _check_acceptances(work_item, client)
        elif work_item.kind == WorkItem.Kind.SEND_MESSAGE:
            _send_message(work_item, client)
        else:
            raise RuntimeError(f"Unsupported work item: {work_item.kind}")
    except (Exception, SystemExit) as error:
        _record_work_failure(work_item, error)
    finally:
        _finish_related_imports(work_item)
    return WorkItem.objects.get(pk=work_item.pk)


def run_due_work(client_factory: ClientFactory | None = None, limit: int = 100) -> int:
    completed = 0
    while completed < limit:
        work_item = run_due_work_once(client_factory)
        if work_item is None:
            break
        completed += 1
    return completed


def recover_interrupted_work() -> int:
    interrupted = list(WorkItem.objects.filter(status=WorkItem.Status.RUNNING))
    for work_item in interrupted:
        work_item.status = WorkItem.Status.NEEDS_REVIEW
        work_item.error = "The app stopped while this action was running. Verify LinkedIn before retrying."
        work_item.completed_at = timezone.now()
        work_item.save(update_fields=["status", "error", "completed_at"])
        if work_item.invitation_id:
            _set_invitation_status(
                work_item.invitation,
                Invitation.Status.NEEDS_REVIEW,
                error=work_item.error,
            )
        if work_item.message_id:
            work_item.message.status = Message.Status.NEEDS_REVIEW
            work_item.message.error = work_item.error
            work_item.message.save(update_fields=["status", "error", "updated_at"])
    return len(interrupted)


def work_status() -> dict:
    running = WorkItem.objects.filter(status=WorkItem.Status.RUNNING).first()
    queued = WorkItem.objects.filter(status=WorkItem.Status.QUEUED).order_by("due_at").first()
    latest = WorkItem.objects.exclude(completed_at=None).order_by("-completed_at").first()
    state = "working" if running else "queued" if queued and queued.due_at <= timezone.now() else "idle"
    return {
        "state": state,
        "current": _work_label(running) if running else None,
        "next_due_at": queued.due_at.isoformat() if queued else None,
        "last_finished_at": latest.completed_at.isoformat() if latest else None,
        "last_work_item_id": str(latest.id) if latest else None,
        "last_status": latest.status if latest else None,
        "last_error": latest.error or None if latest else None,
        "pending_invitations": Invitation.objects.filter(
            status=Invitation.Status.PENDING
        ).count(),
        "accepted_invitations": Invitation.objects.filter(
            status=Invitation.Status.ACCEPTED
        ).count(),
    }


def acceptance_request_snapshot(work_item: WorkItem | None) -> dict:
    return {
        "state": work_item.status if work_item else "no_pending",
        "work_item_id": str(work_item.id) if work_item else None,
        "due_at": work_item.due_at.isoformat() if work_item else None,
    }


def _send_invitation(work_item: WorkItem, client) -> None:
    invitation = Invitation.objects.select_related("person").get(pk=work_item.invitation_id)
    person = invitation.person
    _set_invitation_status(invitation, Invitation.Status.CHECKING)

    pending_ids = {
        public_id.casefold() for public_id in client.get_sent_invitation_public_ids()
    }
    checked_at = timezone.now()
    if person.normalized_public_id in pending_ids:
        _set_invitation_status(
            invitation,
            Invitation.Status.PENDING,
            error="Connection request is already pending.",
            checked_at=checked_at,
            legacy_status=ConnectionRequest.Status.PENDING,
        )
        _succeed(work_item)
        return

    connection_state = client.get_connection_state(person.public_id, name=person.name)
    if connection_state == "connected":
        _set_invitation_status(
            invitation,
            Invitation.Status.ALREADY_CONNECTED,
            error="Already connected.",
            checked_at=checked_at,
        )
        _succeed(work_item)
        return
    if connection_state != "not_connected":
        raise RuntimeError("Connection status could not be confirmed.")

    _set_invitation_status(
        invitation,
        Invitation.Status.SENDING,
        checked_at=checked_at,
    )
    try:
        result = client.add_connection(profile_public_id=person.public_id)
    except Exception as error:
        _needs_review(work_item, invitation, error)
        return

    response_status = int((result or {}).get("status", 0))
    if not 200 <= response_status < 300:
        error = RuntimeError(f"LinkedIn returned status {response_status or 'unknown'}.")
        error.status = response_status or None
        _fail_invitation(work_item, invitation, error)
        return

    _set_invitation_status(
        invitation,
        Invitation.Status.PENDING,
        provider_status=response_status,
        sent_at=timezone.now(),
    )
    _succeed(work_item, provider_status=response_status)
    enqueue_acceptance_check()


def _check_acceptances(work_item: WorkItem, client) -> None:
    invitations = list(
        Invitation.objects.select_related("person")
        .filter(status=Invitation.Status.PENDING, sent_at__isnull=False)
        .order_by("sent_at")
    )
    if not invitations:
        _succeed(work_item)
        return

    since_ms = int(invitations[0].sent_at.timestamp() * 1000)
    recent_connections = client.get_recent_connections(max_results=1000, since_ms=since_ms)
    connected = {
        item.get("public_id", "").casefold(): item
        for item in recent_connections
        if item.get("public_id")
    }
    checked_at = timezone.now()
    for invitation in invitations:
        match = connected.get(invitation.person.normalized_public_id)
        if match:
            connected_at = match.get("connected_at")
            accepted_at = (
                datetime.fromtimestamp(connected_at / 1000, tz=datetime_timezone.utc)
                if isinstance(connected_at, int)
                else checked_at
            )
            _set_invitation_status(
                invitation,
                Invitation.Status.ACCEPTED,
                checked_at=checked_at,
                accepted_at=accepted_at,
            )
            _queue_message_if_enabled(invitation)
        else:
            _set_invitation_status(
                invitation,
                Invitation.Status.PENDING,
                checked_at=checked_at,
            )
    _succeed(work_item)
    enqueue_acceptance_check()


def _queue_message_if_enabled(invitation: Invitation) -> Message | None:
    source_import = (
        ConnectionImport.objects.filter(
            requests__invitation=invitation,
            auto_message_enabled=True,
            message_template__isnull=False,
        )
        .select_related("message_template")
        .order_by("-created_at")
        .first()
    )
    template = source_import.message_template if source_import else None
    if template is None or not template.auto_send_enabled:
        return None

    first_name = invitation.person.name.split()[0] if invitation.person.name else "there"
    body = template.body.replace("{first_name}", first_name)
    message, created = Message.objects.get_or_create(
        invitation=invitation,
        defaults={
            "template": template,
            "body": body,
            "queued_at": timezone.now(),
        },
    )
    if created:
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            invitation=invitation,
            message=message,
            due_at=timezone.now(),
            dedupe_key=f"message:{message.id}",
        )
    return message


def _send_message(work_item: WorkItem, client) -> None:
    message = Message.objects.select_related("invitation__person").get(pk=work_item.message_id)
    message.status = Message.Status.SENDING
    message.save(update_fields=["status", "updated_at"])
    person = message.invitation.person
    profile = client.get_profile(public_id=person.public_id)
    recipient_urn = profile.get("entityUrn", "")
    if not recipient_urn:
        raise RuntimeError("LinkedIn recipient ID could not be found.")
    try:
        result = client.send_message(message_body=message.body, recipients=[recipient_urn])
    except Exception as error:
        message.status = Message.Status.NEEDS_REVIEW
        message.error = str(error) or "Message delivery is uncertain."
        message.save(update_fields=["status", "error", "updated_at"])
        work_item.status = WorkItem.Status.NEEDS_REVIEW
        work_item.error = message.error
        work_item.completed_at = timezone.now()
        work_item.save(update_fields=["status", "error", "completed_at"])
        return

    response_status = int((result or {}).get("status", 0))
    if not 200 <= response_status < 300:
        error = RuntimeError(f"LinkedIn returned status {response_status or 'unknown'}.")
        error.status = response_status or None
        raise error
    message.status = Message.Status.SENT
    message.provider_status = response_status
    message.sent_at = timezone.now()
    message.error = ""
    message.save(
        update_fields=["status", "provider_status", "sent_at", "error", "updated_at"]
    )
    _succeed(work_item, provider_status=response_status)


def _set_invitation_status(
    invitation: Invitation,
    status: str,
    *,
    error: str = "",
    provider_status: int | None = None,
    sent_at=None,
    accepted_at=None,
    checked_at=None,
    legacy_status: str | None = None,
) -> None:
    invitation.status = status
    invitation.error = error
    invitation.provider_status = provider_status
    if sent_at is not None:
        invitation.sent_at = sent_at
    if accepted_at is not None:
        invitation.accepted_at = accepted_at
    if checked_at is not None:
        invitation.checked_at = checked_at
    invitation.save()

    if legacy_status is None:
        legacy_status = {
            Invitation.Status.QUEUED: ConnectionRequest.Status.READY,
            Invitation.Status.CHECKING: ConnectionRequest.Status.CHECKING,
            Invitation.Status.SENDING: ConnectionRequest.Status.SENDING,
            Invitation.Status.PENDING: ConnectionRequest.Status.SENT,
            Invitation.Status.ACCEPTED: ConnectionRequest.Status.ACCEPTED,
            Invitation.Status.ALREADY_CONNECTED: ConnectionRequest.Status.CONNECTED,
            Invitation.Status.FAILED: ConnectionRequest.Status.FAILED,
            Invitation.Status.NEEDS_REVIEW: ConnectionRequest.Status.FAILED,
            Invitation.Status.CANCELLED: ConnectionRequest.Status.SKIPPED,
        }[status]
    invitation.import_rows.update(
        status=legacy_status,
        error=error,
        provider_status=provider_status,
        sent_at=invitation.sent_at,
        accepted_at=invitation.accepted_at,
        checked_at=invitation.checked_at,
    )


def _succeed(work_item: WorkItem, provider_status: int | None = None) -> None:
    work_item.status = WorkItem.Status.SUCCEEDED
    work_item.provider_status = provider_status
    work_item.error = ""
    work_item.completed_at = timezone.now()
    work_item.save(update_fields=["status", "provider_status", "error", "completed_at"])


def _needs_review(work_item: WorkItem, invitation: Invitation, error: Exception) -> None:
    detail = str(error) or "Invitation delivery is uncertain."
    provider_status = _provider_status(error)
    _set_invitation_status(
        invitation,
        Invitation.Status.NEEDS_REVIEW,
        error=detail,
        provider_status=provider_status,
    )
    work_item.status = WorkItem.Status.NEEDS_REVIEW
    work_item.error = detail
    work_item.provider_status = provider_status
    work_item.completed_at = timezone.now()
    work_item.save(
        update_fields=["status", "error", "provider_status", "completed_at"]
    )


def _fail_invitation(work_item: WorkItem, invitation: Invitation, error: Exception) -> None:
    detail = str(error) or "Invitation failed."
    provider_status = _provider_status(error)
    _set_invitation_status(
        invitation,
        Invitation.Status.FAILED,
        error=detail,
        provider_status=provider_status,
    )
    work_item.status = WorkItem.Status.FAILED
    work_item.error = detail
    work_item.provider_status = provider_status
    work_item.completed_at = timezone.now()
    work_item.save(
        update_fields=["status", "error", "provider_status", "completed_at"]
    )


def _record_work_failure(work_item: WorkItem, error: BaseException) -> None:
    detail = str(error) or "Work failed."
    provider_status = _provider_status(error)
    if work_item.invitation_id and work_item.kind == WorkItem.Kind.SEND_INVITATION:
        invitation = Invitation.objects.get(pk=work_item.invitation_id)
        _fail_invitation(work_item, invitation, error)
        return
    if work_item.message_id:
        message = Message.objects.get(pk=work_item.message_id)
        message.status = Message.Status.FAILED
        message.error = detail
        message.provider_status = provider_status
        message.save(update_fields=["status", "error", "provider_status", "updated_at"])
    work_item.status = WorkItem.Status.FAILED
    work_item.error = detail
    work_item.provider_status = provider_status
    work_item.completed_at = timezone.now()
    work_item.save(
        update_fields=["status", "error", "provider_status", "completed_at"]
    )


def _provider_status(error: BaseException) -> int | None:
    status = getattr(error, "status", None)
    return status if isinstance(status, int) and 100 <= status <= 599 else None


def _finish_related_imports(work_item: WorkItem) -> None:
    if not work_item.invitation_id:
        return
    imports = ConnectionImport.objects.filter(
        requests__invitation_id=work_item.invitation_id
    ).distinct()
    for connection_import in imports:
        has_active_work = WorkItem.objects.filter(
            invitation__import_rows__connection_import=connection_import,
            status__in=[WorkItem.Status.QUEUED, WorkItem.Status.RUNNING],
        ).exists()
        if not has_active_work and connection_import.status != ConnectionImport.Status.COMPLETE:
            connection_import.status = ConnectionImport.Status.COMPLETE
            connection_import.completed_at = timezone.now()
            connection_import.save(update_fields=["status", "completed_at"])


def _work_label(work_item: WorkItem | None) -> str | None:
    if work_item is None:
        return None
    if work_item.invitation_id:
        name = work_item.invitation.person.name
        if work_item.kind == WorkItem.Kind.SEND_MESSAGE:
            return f"Sending message to {name}"
        return f"Checking invitation for {name}"
    if work_item.kind == WorkItem.Kind.CHECK_ACCEPTANCES:
        return "Checking accepted invitations"
    return work_item.get_kind_display()
