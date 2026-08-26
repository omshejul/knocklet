import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.db import transaction
from django.utils import timezone
from python_calamine import CalamineError, CalamineWorkbook

from .automation import queue_invitation, run_due_work
from .models import ConnectionImport, ConnectionRequest, Invitation, MessageTemplate

MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 100
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".xlsb", ".xlsm", ".ods"}
SUPPORTED_EXTENSIONS = {".csv", *SPREADSHEET_EXTENSIONS}


class ImportFileError(ValueError):
    pass


class ImportNotFound(Exception):
    pass


class ImportConflict(Exception):
    pass


class AcceptanceCheckError(Exception):
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


def _find_header_index(headers: list[str], candidates: set[str]) -> int | None:
    for index, header in enumerate(headers):
        if _normalize_header(header) in candidates:
            return index
    return None


def _find_linkedin_header_index(headers: list[str]) -> int | None:
    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if "linkedin" in normalized and (
            "url" in normalized or "profile" in normalized or normalized == "linkedin"
        ):
            return index
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


def _cell_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _row_value(row: list[object], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return _cell_text(row[index])


def _linkedin_column_index(headers: list[str], rows: list[list[object]]) -> int | None:
    header_index = _find_linkedin_header_index(headers)
    if header_index is not None:
        return header_index

    scores = [0] * len(headers)
    for row in rows:
        for index in range(min(len(row), len(headers))):
            if _public_id(_cell_text(row[index])):
                scores[index] += 1
    if not scores or max(scores) == 0:
        return None
    return scores.index(max(scores))


def _sheet_score(rows: list[list[object]]) -> tuple[int, int]:
    if len(rows) < 2:
        return (0, 0)
    headers = [_cell_text(value) for value in rows[0]]
    header_match = _find_linkedin_header_index(headers) is not None
    linkedin_index = _linkedin_column_index(headers, rows[1:])
    valid_urls = (
        sum(_public_id(_row_value(row, linkedin_index)) is not None for row in rows[1:])
        if linkedin_index is not None
        else 0
    )
    return (valid_urls, int(header_match))


def _read_csv_rows(data: bytes) -> list[list[object]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportFileError("CSV must use UTF-8 encoding.") from error

    try:
        return [list(row) for row in csv.reader(io.StringIO(text))]
    except csv.Error as error:
        raise ImportFileError("CSV could not be read.") from error


def _read_spreadsheet_rows(data: bytes) -> list[list[object]]:
    try:
        workbook = CalamineWorkbook.from_filelike(io.BytesIO(data))
        sheets = [
            workbook.get_sheet_by_name(name).to_python()
            for name in workbook.sheet_names
        ]
    except CalamineError as error:
        raise ImportFileError("Spreadsheet could not be read.") from error

    populated_sheets = [rows for rows in sheets if rows]
    if not populated_sheets:
        raise ImportFileError("Spreadsheet has no rows.")
    return max(populated_sheets, key=_sheet_score)


def parse_connection_file(data: bytes, filename: str) -> ParsedImport:
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportFileError("File must be smaller than 2 MB.")

    extension = Path(filename).suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ImportFileError("Use a CSV, XLS, XLSX, XLSB, XLSM, or ODS file.")

    rows = _read_csv_rows(data) if extension == ".csv" else _read_spreadsheet_rows(data)
    if not rows:
        raise ImportFileError("File has no header row.")

    headers = [_cell_text(value) for value in rows[0]]
    if not any(headers):
        raise ImportFileError("File has no header row.")

    linkedin_index = _linkedin_column_index(headers, rows[1:])
    if linkedin_index is None:
        raise ImportFileError("File has no LinkedIn profile URLs.")

    name_index = _find_header_index(headers, {"name", "fullname", "personname"})
    first_name_index = _find_header_index(headers, {"firstname", "first"})
    last_name_index = _find_header_index(headers, {"lastname", "last"})

    people: list[ParsedPerson] = []
    seen_public_ids: set[str] = set()
    for row_number, row in enumerate(rows[1:], start=2):
        if len(people) >= MAX_IMPORT_ROWS:
            raise ImportFileError("File can contain at most 100 people.")
        if not any(_cell_text(value) for value in row):
            continue

        linkedin_url = _row_value(row, linkedin_index)
        public_id = _public_id(linkedin_url)
        full_name = _row_value(row, name_index)
        if full_name.casefold() in {"[object object]", "object"}:
            full_name = ""
        if not full_name:
            first_name = _row_value(row, first_name_index)
            last_name = _row_value(row, last_name_index)
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
        raise ImportFileError("File has no people.")

    return ParsedImport(filename=filename, people=people)


ClientFactory = Callable[[], object]


class ConnectionImportStore:
    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self.client_factory = client_factory or self._get_client

    @staticmethod
    def _get_client():
        from auth import get_client

        return get_client()

    def create(self, data: bytes, filename: str) -> dict:
        parsed = parse_connection_file(data, filename)
        ready_public_ids = [
            person.public_id.casefold()
            for person in parsed.people
            if person.status == "ready"
        ]
        previously_sent = set(
            Invitation.objects.filter(
                person__normalized_public_id__in=ready_public_ids,
                status__in=[
                    Invitation.Status.QUEUED,
                    Invitation.Status.CHECKING,
                    Invitation.Status.SENDING,
                    Invitation.Status.PENDING,
                    Invitation.Status.ACCEPTED,
                    Invitation.Status.ALREADY_CONNECTED,
                    Invitation.Status.NEEDS_REVIEW,
                ],
            ).values_list("person__normalized_public_id", flat=True)
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
                            if person.public_id.casefold() in previously_sent
                            and person.status == "ready"
                            else person.status
                        ),
                        error=(
                            "Connection request was already sent."
                            if person.public_id.casefold() in previously_sent
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

    def list_imports(self, limit: int = 20) -> list[dict]:
        imports = ConnectionImport.objects.prefetch_related("requests")[:limit]
        return [self._snapshot(connection_import) for connection_import in imports]

    def approve(
        self,
        import_id: str,
        row_numbers: list[int] | None = None,
    ) -> dict:
        with transaction.atomic():
            try:
                connection_import = ConnectionImport.objects.select_for_update().get(
                    pk=import_id
                )
            except (ConnectionImport.DoesNotExist, ValueError):
                raise ImportNotFound from None
            if connection_import.status != ConnectionImport.Status.AWAITING_APPROVAL:
                raise ImportConflict

            ready_requests = connection_import.requests.filter(
                status=ConnectionRequest.Status.READY
            )
            selected_rows = (
                set(row_numbers)
                if row_numbers is not None
                else set(ready_requests.values_list("row_number", flat=True))
            )
            selected_requests = ready_requests.filter(
                row_number__in=selected_rows
            )
            if (
                not selected_rows
                or selected_requests.count() != len(selected_rows)
            ):
                raise ImportConflict

            ready_ids = list(selected_requests.values_list("id", flat=True))
            connection_import.requests.exclude(
                row_number__in=selected_rows
            ).delete()

            connection_import.status = ConnectionImport.Status.CHECKING
            connection_import.approved_at = timezone.now()
            template = MessageTemplate.objects.filter(
                is_active=True,
                auto_send_enabled=True,
            ).first()
            if template:
                connection_import.message_template = template
                connection_import.message_template_body = template.body
                connection_import.auto_message_enabled = True
            connection_import.save(
                update_fields=[
                    "status",
                    "approved_at",
                    "message_template",
                    "message_template_body",
                    "auto_message_enabled",
                ]
            )
            for connection_request in ConnectionRequest.objects.filter(id__in=ready_ids):
                queue_invitation(connection_request)

        return self.get(import_id)

    def wait(self, import_id: str, timeout: float = 5) -> dict:
        run_due_work(self.client_factory)
        return self.get(import_id)

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
        total_count = sum(
            person["status"] not in {"invalid", "duplicate", "skipped"}
            for person in people
        )
        checked_count = sum(person["checked_at"] is not None for person in people)
        processed_count = sum(
            person["status"] in {"pending", "connected", "sent", "accepted", "failed"}
            for person in people
        )
        if connection_import.status == ConnectionImport.Status.CHECKING:
            progress_percent = round(
                checked_count / total_count * 50 if total_count else 50
            )
        elif connection_import.status == ConnectionImport.Status.SENDING:
            progress_percent = round(
                50 + processed_count / total_count * 50 if total_count else 100
            )
        elif connection_import.status == ConnectionImport.Status.COMPLETE:
            progress_percent = 100
        else:
            progress_percent = 0
        return {
            "id": str(connection_import.id),
            "filename": connection_import.filename,
            "status": connection_import.status,
            "people": people,
            "ready_count": sum(person["status"] == "ready" for person in people),
            "sent_count": sum(
                person["status"] in {"sent", "accepted"} for person in people
            ),
            "accepted_count": sum(person["status"] == "accepted" for person in people),
            "pending_count": sum(person["status"] == "pending" for person in people),
            "connected_count": sum(
                person["status"] == "connected" for person in people
            ),
            "failed_count": sum(person["status"] == "failed" for person in people),
            "skipped_count": sum(
                person["status"]
                in {"invalid", "duplicate", "skipped", "pending", "connected"}
                for person in people
            ),
            "total_count": total_count,
            "checked_count": checked_count,
            "processed_count": processed_count,
            "progress_percent": progress_percent,
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
