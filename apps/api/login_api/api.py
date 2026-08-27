from typing import Literal

from django.core.exceptions import ValidationError
from django.db.models import Q
from ninja import File, NinjaAPI, Schema, Status
from ninja.files import UploadedFile

from .activity import list_logs
from .automation import (
    acceptance_request_snapshot,
    enqueue_acceptance_check,
    queue_messages_for_people,
    resolve_needs_review_for_person,
    retry_invitation_for_person,
    work_item_status,
    work_status,
)
from .cli_login import LoginAlreadyRunning, LoginManager
from .connection_imports import (
    ConnectionImportStore,
    ImportConflict,
    ImportFileError,
    ImportNotFound,
)
from .outreach import list_people
from .message_templates import (
    get_active_template,
    list_template_fields,
    save_active_template,
)
from .models import Person, WorkItem


class HealthOut(Schema):
    status: Literal["ok"]


class LoginStatusOut(Schema):
    status: Literal["idle", "waiting", "authenticated", "failed"]
    message: str
    started_at: str | None
    updated_at: str


class PersonOut(Schema):
    row_number: int
    name: str
    linkedin_url: str
    public_id: str
    status: str
    error: str | None
    provider_status: int | None
    sent_at: str | None
    accepted_at: str | None
    checked_at: str | None


class ConnectionImportOut(Schema):
    id: str
    filename: str
    status: str
    people: list[PersonOut]
    ready_count: int
    sent_count: int
    accepted_count: int
    pending_count: int
    connected_count: int
    failed_count: int
    skipped_count: int
    total_count: int
    checked_count: int
    processed_count: int
    progress_percent: int
    created_at: str
    approved_at: str | None
    completed_at: str | None


class ErrorOut(Schema):
    detail: str


class AcceptanceRequestOut(Schema):
    state: str
    work_item_id: str | None
    due_at: str | None


class WorkerStatusOut(Schema):
    state: str
    current: str | None
    next_due_at: str | None
    last_finished_at: str | None
    last_work_item_id: str | None
    last_status: str | None
    last_error: str | None
    last_acceptance_check_at: str | None
    next_acceptance_check_at: str | None
    pending_invitations: int
    accepted_invitations: int


class WorkItemStatusOut(Schema):
    id: str
    kind: str
    status: str
    error: str | None
    started_at: str | None
    completed_at: str | None


class ActivityLogOut(Schema):
    id: str
    kind: str
    status: str
    person_name: str | None
    error: str | None
    provider_status: int | None
    attempt_count: int
    activity_at: str
    due_at: str
    created_at: str
    started_at: str | None
    completed_at: str | None


class ActivityLogPageOut(Schema):
    items: list[ActivityLogOut]
    has_more: bool
    next_offset: int | None


class ConnectionApprovalIn(Schema):
    row_numbers: list[int]


class OutreachPersonOut(Schema):
    id: str
    name: str
    first_name: str
    linkedin_url: str
    public_id: str
    invitation_status: str
    invitation_error: str | None
    invitation_provider_status: int | None
    sent_at: str | None
    accepted_at: str | None
    checked_at: str | None
    message_status: str
    message_error: str | None
    message_body: str | None
    message_due_at: str | None
    message_sent_at: str | None
    last_activity_at: str


class MessageTemplateIn(Schema):
    name: str = "Follow-up"
    body: str
    auto_send_enabled: bool = False
    delay_minutes: int = 5


class MessageTemplateOut(Schema):
    id: str
    name: str
    body: str
    is_active: bool
    auto_send_enabled: bool
    delay_minutes: int
    updated_at: str


class MessageTemplateFieldOut(Schema):
    name: str
    label: str
    placeholder: str


class PersonMessageIn(Schema):
    person_ids: list[str]


class PersonMessageOut(Schema):
    queued_count: int


class PersonFirstNameIn(Schema):
    first_name: str


class PersonFirstNameOut(Schema):
    id: str
    first_name: str


class ReviewResolutionIn(Schema):
    outcome: Literal["sent", "not_sent"]


class PersonActionOut(Schema):
    kind: str
    status: str


api = NinjaAPI(title="Knocklet local API", version="0.1.0")
login_manager = LoginManager()
connection_imports = ConnectionImportStore()


@api.get("/health", response=HealthOut)
def health(request):
    return {"status": "ok"}


@api.get("/auth/status", response=LoginStatusOut)
def auth_status(request):
    return login_manager.status().to_dict()


@api.post("/auth/login", response={202: LoginStatusOut, 409: LoginStatusOut})
def start_login(request):
    try:
        return Status(202, login_manager.start().to_dict())
    except LoginAlreadyRunning:
        return Status(409, login_manager.status().to_dict())


@api.post("/connections/import", response={201: ConnectionImportOut, 400: ErrorOut})
def import_connections(request, csv_file: File[UploadedFile]):
    try:
        connection_import = connection_imports.create(csv_file.read(), csv_file.name)
        return Status(201, connection_import)
    except ImportFileError as error:
        return Status(400, {"detail": str(error)})


@api.get("/connections/imports", response=list[ConnectionImportOut])
def connection_import_history(request):
    return connection_imports.list_imports()


@api.post(
    "/connections/acceptance/refresh",
    response={202: AcceptanceRequestOut, 200: AcceptanceRequestOut},
)
def refresh_connection_acceptance(request):
    work_item = enqueue_acceptance_check(force=True)
    response = acceptance_request_snapshot(work_item)
    return Status(202 if work_item else 200, response)


@api.get("/automation/status", response=WorkerStatusOut)
def automation_status(request):
    return work_status()


@api.get(
    "/automation/work/{work_item_id}",
    response={200: WorkItemStatusOut, 404: ErrorOut},
)
def automation_work_item(request, work_item_id: str):
    item = work_item_status(work_item_id)
    return item if item else Status(404, {"detail": "Work item not found."})


@api.get("/people", response=list[OutreachPersonOut])
def people(request):
    return list_people()


@api.post(
    "/people/messages",
    response={202: PersonMessageOut, 404: ErrorOut, 409: ErrorOut},
)
def queue_person_messages(request, payload: PersonMessageIn):
    try:
        queued_count = queue_messages_for_people(payload.person_ids)
    except (Person.DoesNotExist, ValidationError):
        return Status(404, {"detail": "Person not found."})
    except ValueError as error:
        return Status(409, {"detail": str(error)})
    return Status(202, {"queued_count": queued_count})


@api.patch(
    "/people/{person_id}",
    response={200: PersonFirstNameOut, 400: ErrorOut, 404: ErrorOut},
)
def update_person_first_name(request, person_id: str, payload: PersonFirstNameIn):
    try:
        person = Person.objects.get(pk=person_id)
    except (Person.DoesNotExist, ValidationError, ValueError):
        return Status(404, {"detail": "Person not found."})

    first_name = payload.first_name.strip()
    if not first_name:
        return Status(400, {"detail": "First name is required."})
    if len(first_name) > 255:
        return Status(400, {"detail": "First name must be 255 characters or fewer."})

    person.first_name = first_name
    person.save(update_fields=["first_name", "updated_at"])
    return {"id": str(person.id), "first_name": person.first_name}


@api.post(
    "/people/{person_id}/invitation/retry",
    response={202: PersonActionOut, 404: ErrorOut, 409: ErrorOut},
)
def retry_person_invitation(request, person_id: str):
    try:
        return Status(202, retry_invitation_for_person(person_id))
    except (Person.DoesNotExist, ValidationError):
        return Status(404, {"detail": "Person not found."})
    except ValueError as error:
        return Status(409, {"detail": str(error)})


@api.post(
    "/people/{person_id}/review",
    response={200: PersonActionOut, 202: PersonActionOut, 404: ErrorOut, 409: ErrorOut},
)
def resolve_person_review(
    request,
    person_id: str,
    payload: ReviewResolutionIn,
):
    try:
        result = resolve_needs_review_for_person(person_id, payload.outcome)
    except (Person.DoesNotExist, ValidationError):
        return Status(404, {"detail": "Person not found."})
    except ValueError as error:
        return Status(409, {"detail": str(error)})
    return Status(200 if payload.outcome == "sent" else 202, result)


@api.get("/logs", response={200: ActivityLogPageOut, 400: ErrorOut})
def logs(
    request,
    limit: int = 50,
    offset: int = 0,
    search: str = "",
    status: str = "",
    kind: str = "",
):
    if offset < 0 or not 1 <= limit <= 1000:
        return Status(
            400,
            {
                "detail": (
                    "Log offset must be zero or greater and limit must be between 1 and 1000."
                )
            },
        )
    return list_logs(
        limit=limit,
        offset=offset,
        search=search,
        status=status,
        kind=kind,
    )


@api.delete(
    "/people/{person_id}",
    response={204: None, 404: ErrorOut, 409: ErrorOut},
)
def delete_person(request, person_id: str):
    try:
        person = Person.objects.get(pk=person_id)
    except (Person.DoesNotExist, ValidationError, ValueError):
        return Status(404, {"detail": "Person not found."})

    active_work = WorkItem.objects.filter(status=WorkItem.Status.RUNNING).filter(
        Q(kind=WorkItem.Kind.CHECK_ACCEPTANCES)
        | Q(invitation__person=person)
        | Q(message__invitation__person=person)
    )
    if active_work.exists():
        return Status(409, {"detail": "Wait for the current action to finish."})

    person.delete()
    return Status(204, None)


@api.get("/message-template", response={200: MessageTemplateOut, 204: None})
def message_template(request):
    template = get_active_template()
    return template if template else Status(204, None)


@api.get("/message-template/fields", response=list[MessageTemplateFieldOut])
def message_template_fields(request):
    return list_template_fields()


@api.put(
    "/message-template",
    response={200: MessageTemplateOut, 400: ErrorOut},
)
def update_message_template(request, payload: MessageTemplateIn):
    try:
        return save_active_template(
            name=payload.name,
            body=payload.body,
            auto_send_enabled=payload.auto_send_enabled,
            delay_minutes=payload.delay_minutes,
        )
    except ValueError as error:
        return Status(400, {"detail": str(error)})


@api.get(
    "/connections/import/{import_id}",
    response={200: ConnectionImportOut, 404: ErrorOut},
)
def connection_import_status(request, import_id: str):
    try:
        return connection_imports.get(import_id)
    except ImportNotFound:
        return Status(404, {"detail": "Import not found."})


@api.post(
    "/connections/import/{import_id}/approve",
    response={202: ConnectionImportOut, 404: ErrorOut, 409: ErrorOut},
)
def approve_connection_import(
    request,
    import_id: str,
    approval: ConnectionApprovalIn,
):
    try:
        return Status(
            202,
            connection_imports.approve(import_id, approval.row_numbers),
        )
    except ImportNotFound:
        return Status(404, {"detail": "Import not found."})
    except ImportConflict:
        return Status(409, {"detail": "Import cannot be sent."})
