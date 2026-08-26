from typing import Literal

from ninja import File, NinjaAPI, Schema, Status
from ninja.files import UploadedFile

from .cli_login import LoginAlreadyRunning, LoginManager
from .connection_imports import (
    AcceptanceCheckError,
    ConnectionImportStore,
    ImportConflict,
    ImportFileError,
    ImportNotFound,
)


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


class AcceptanceRefreshOut(Schema):
    checked_count: int
    accepted_count: int
    pending_count: int
    checked_at: str


api = NinjaAPI(title="LinkedIn CLI local API", version="0.1.0")
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
    response={200: AcceptanceRefreshOut, 502: ErrorOut},
)
def refresh_connection_acceptance(request):
    try:
        return connection_imports.refresh_acceptance()
    except AcceptanceCheckError as error:
        return Status(502, {"detail": str(error)})


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
def approve_connection_import(request, import_id: str):
    try:
        return Status(202, connection_imports.approve(import_id))
    except ImportNotFound:
        return Status(404, {"detail": "Import not found."})
    except ImportConflict:
        return Status(409, {"detail": "Import cannot be sent."})
