import csv
import io
import threading
from dataclasses import dataclass
from typing import Callable
from urllib.parse import unquote, urlparse

from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import ConnectionImport, ConnectionRequest


MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 100


class CsvImportError(ValueError):
    pass


class ImportNotFound(Exception):
    pass


class ImportConflict(Exception):
    pass


@dataclass(frozen=True)
class ParsedPerson:
    row_number: int
    name: str
    linkedin_url: str
    public_id: str
    status: str
    error: str | None = None


@dataclass(frozen=True)
class ParsedImport:
    filename: str
    people: list[ParsedPerson]


def _normalize_header(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _find_header(headers: list[str], candidates: set[str]) -> str | None:
    for header in headers:
        if _normalize_header(header) in candidates:
            return header
    return None


def _find_linkedin_header(headers: list[str]) -> str | None:
    for header in headers:
        normalized = _normalize_header(header)
        if "linkedin" in normalized and (
            "url" in normalized or "profile" in normalized or normalized == "linkedin"
        ):
            return header
    return None


def _public_id(linkedin_url: str) -> str | None:
    value = linkedin_url.strip()
    if not value:
        return None
    if "://" not in value:
        value = "https://" + value

    parsed = urlparse(value)
    hostname = (parsed.hostname or "").casefold()
    parts = [part for part in parsed.path.split("/") if part]
    if not hostname.endswith("linkedin.com") or len(parts) < 2 or parts[0] != "in":
        return None

    public_id = unquote(parts[1]).strip()
    return public_id or None


def parse_clay_csv(data: bytes, filename: str) -> ParsedImport:
    if len(data) > MAX_CSV_BYTES:
        raise CsvImportError("CSV must be smaller than 2 MB.")

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvImportError("CSV must use UTF-8 encoding.") from error

    reader = csv.DictReader(io.StringIO(text))
    headers = [header for header in reader.fieldnames or [] if header]
    if not headers:
        raise CsvImportError("CSV has no header row.")

    linkedin_header = _find_linkedin_header(headers)
    if linkedin_header is None:
        raise CsvImportError("CSV needs a LinkedIn URL column.")

    name_header = _find_header(headers, {"name", "fullname", "personname"})
    first_name_header = _find_header(headers, {"firstname", "first"})
    last_name_header = _find_header(headers, {"lastname", "last"})

    people: list[ParsedPerson] = []
    seen_public_ids: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        if len(people) >= MAX_CSV_ROWS:
            raise CsvImportError("CSV can contain at most 100 people.")
        if not any((value or "").strip() for value in row.values()):
            continue

        linkedin_url = (row.get(linkedin_header) or "").strip()
        public_id = _public_id(linkedin_url)
        full_name = (row.get(name_header) or "").strip() if name_header else ""
        if full_name.casefold() in {"[object object]", "object"}:
            full_name = ""
        if not full_name:
            first_name = (
                (row.get(first_name_header) or "").strip() if first_name_header else ""
            )
            last_name = (
                (row.get(last_name_header) or "").strip() if last_name_header else ""
            )
            full_name = " ".join(part for part in [first_name, last_name] if part)

        if public_id is None:
            people.append(
                ParsedPerson(
                    row_number=row_number,
                    name=full_name or "Unknown person",
                    linkedin_url=linkedin_url,
                    public_id="",
                    status="invalid",
                    error="Missing or invalid LinkedIn profile URL.",
                )
            )
            continue

        if public_id.casefold() in seen_public_ids:
            people.append(
                ParsedPerson(
                    row_number=row_number,
                    name=full_name or public_id,
                    linkedin_url=linkedin_url,
                    public_id=public_id,
                    status="duplicate",
                    error="Duplicate profile.",
                )
            )
            continue

        seen_public_ids.add(public_id.casefold())
        people.append(
            ParsedPerson(
                row_number=row_number,
                name=full_name or public_id,
                linkedin_url=linkedin_url,
                public_id=public_id,
                status="ready",
            )
        )

    if not people:
        raise CsvImportError("CSV has no people.")

    return ParsedImport(filename=filename, people=people)


ClientFactory = Callable[[], object]


class ConnectionImportStore:
    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self.client_factory = client_factory or self._get_client
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _get_client():
        from auth import get_client

        return get_client()

    def create(self, data: bytes, filename: str) -> dict:
        parsed = parse_clay_csv(data, filename)
        ready_public_ids = [
            person.public_id for person in parsed.people if person.status == "ready"
        ]
        previously_sent = set(
            ConnectionRequest.objects.filter(
                public_id__in=ready_public_ids,
                status__in=[
                    ConnectionRequest.Status.SENDING,
                    ConnectionRequest.Status.SENT,
                    ConnectionRequest.Status.ACCEPTED,
                ],
            ).values_list("public_id", flat=True)
        )

        with transaction.atomic():
            connection_import = ConnectionImport.objects.create(
                filename=parsed.filename
            )
            ConnectionRequest.objects.bulk_create(
                [
                    ConnectionRequest(
                        connection_import=connection_import,
                        row_number=person.row_number,
                        name=person.name,
                        linkedin_url=person.linkedin_url,
                        public_id=person.public_id,
                        status=(
                            ConnectionRequest.Status.DUPLICATE
                            if person.public_id in previously_sent
                            and person.status == "ready"
                            else person.status
                        ),
                        error=(
                            "Connection request was already sent."
                            if person.public_id in previously_sent
                            and person.status == "ready"
                            else person.error or ""
                        ),
                    )
                    for person in parsed.people
                ]
            )
        return self.get(str(connection_import.id))

    def get(self, import_id: str) -> dict:
        try:
            connection_import = ConnectionImport.objects.prefetch_related(
                "requests"
            ).get(pk=import_id)
        except (ConnectionImport.DoesNotExist, ValueError):
            raise ImportNotFound from None
        return self._snapshot(connection_import)

    def approve(self, import_id: str) -> dict:
        with transaction.atomic():
            try:
                connection_import = ConnectionImport.objects.select_for_update().get(
                    pk=import_id
                )
            except (ConnectionImport.DoesNotExist, ValueError):
                raise ImportNotFound from None
            if connection_import.status != ConnectionImport.Status.AWAITING_APPROVAL:
                raise ImportConflict

            ready_ids = list(
                connection_import.requests.filter(
                    status=ConnectionRequest.Status.READY
                ).values_list("id", flat=True)
            )
            if not ready_ids:
                raise ImportConflict

            connection_import.status = ConnectionImport.Status.SENDING
            connection_import.approved_at = timezone.now()
            connection_import.save(update_fields=["status", "approved_at"])

        thread = threading.Thread(
            target=self._send_requests,
            args=(str(connection_import.id), ready_ids),
            daemon=True,
        )
        with self._lock:
            self._threads[import_id] = thread

        thread.start()
        return self.get(import_id)

    def wait(self, import_id: str, timeout: float = 5) -> dict:
        with self._lock:
            thread = self._threads.get(import_id)
        if thread is not None:
            thread.join(timeout)
        return self.get(import_id)

    def _send_requests(self, import_id: str, request_ids: list[int]) -> None:
        close_old_connections()
        try:
            client = self.client_factory()
        except Exception:
            self._fail_remaining(import_id, "LinkedIn session could not be opened.")
            return

        for request_id in request_ids:
            connection_request = ConnectionRequest.objects.get(pk=request_id)
            connection_request.status = ConnectionRequest.Status.SENDING
            connection_request.save(update_fields=["status"])

            try:
                result = client.add_connection(
                    profile_public_id=connection_request.public_id
                )
                response_status = int((result or {}).get("status", 0))
                sent = 200 <= response_status < 300
                error = (
                    ""
                    if sent
                    else f"LinkedIn returned status {response_status or 'unknown'}."
                )
            except Exception as request_error:
                sent = False
                response_status = None
                error = str(request_error) or "Request failed."

            connection_request.status = (
                ConnectionRequest.Status.SENT
                if sent
                else ConnectionRequest.Status.FAILED
            )
            connection_request.error = error
            connection_request.provider_status = response_status
            connection_request.sent_at = timezone.now() if sent else None
            connection_request.save(
                update_fields=[
                    "status",
                    "error",
                    "provider_status",
                    "sent_at",
                ]
            )

        ConnectionImport.objects.filter(pk=import_id).update(
            status=ConnectionImport.Status.COMPLETE,
            completed_at=timezone.now(),
        )
        close_old_connections()

    def _fail_remaining(self, import_id: str, error: str) -> None:
        ConnectionRequest.objects.filter(
            connection_import_id=import_id,
            status__in=[
                ConnectionRequest.Status.READY,
                ConnectionRequest.Status.SENDING,
            ],
        ).update(status=ConnectionRequest.Status.FAILED, error=error)
        ConnectionImport.objects.filter(pk=import_id).update(
            status=ConnectionImport.Status.COMPLETE,
            completed_at=timezone.now(),
        )
        close_old_connections()

    @staticmethod
    def _snapshot(connection_import: ConnectionImport) -> dict:
        people = [
            {
                "row_number": request.row_number,
                "name": request.name,
                "linkedin_url": request.linkedin_url,
                "public_id": request.public_id,
                "status": request.status,
                "error": request.error or None,
                "provider_status": request.provider_status,
                "sent_at": request.sent_at.isoformat() if request.sent_at else None,
                "accepted_at": (
                    request.accepted_at.isoformat() if request.accepted_at else None
                ),
                "checked_at": (
                    request.checked_at.isoformat() if request.checked_at else None
                ),
            }
            for request in connection_import.requests.all()
        ]
        return {
            "id": str(connection_import.id),
            "filename": connection_import.filename,
            "status": connection_import.status,
            "people": people,
            "ready_count": sum(person["status"] == "ready" for person in people),
            "sent_count": sum(
                person["status"] in {"sent", "accepted"} for person in people
            ),
            "accepted_count": sum(
                person["status"] == "accepted" for person in people
            ),
            "failed_count": sum(person["status"] == "failed" for person in people),
            "skipped_count": sum(
                person["status"] in {"invalid", "duplicate"} for person in people
            ),
            "created_at": connection_import.created_at.isoformat(),
            "approved_at": (
                connection_import.approved_at.isoformat()
                if connection_import.approved_at
                else None
            ),
            "completed_at": (
                connection_import.completed_at.isoformat()
                if connection_import.completed_at
                else None
            ),
        }
