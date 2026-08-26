import csv
import io
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as datetime_timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.db import close_old_connections, transaction
from django.utils import timezone
from python_calamine import CalamineError, CalamineWorkbook

from .models import ConnectionImport, ConnectionRequest

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
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _get_client():
        from auth import get_client

        return get_client()

    def create(self, data: bytes, filename: str) -> dict:
        parsed = parse_connection_file(data, filename)
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
                    ConnectionRequest.Status.PENDING,
                    ConnectionRequest.Status.CONNECTED,
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

    def list_imports(self, limit: int = 20) -> list[dict]:
        imports = ConnectionImport.objects.prefetch_related("requests")[:limit]
        return [self._snapshot(connection_import) for connection_import in imports]

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

            connection_import.status = ConnectionImport.Status.CHECKING
            connection_import.approved_at = timezone.now()
            connection_import.save(update_fields=["status", "approved_at"])

        thread = threading.Thread(
            target=self._check_and_send_requests,
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

    def refresh_acceptance(self) -> dict:
        sent_requests = list(
            ConnectionRequest.objects.filter(
                status=ConnectionRequest.Status.SENT,
                sent_at__isnull=False,
            ).order_by("sent_at")
        )
        checked_at = timezone.now()
        if not sent_requests:
            return {
                "checked_count": 0,
                "accepted_count": 0,
                "pending_count": 0,
                "checked_at": checked_at.isoformat(),
            }

        since_ms = int(sent_requests[0].sent_at.timestamp() * 1000)
        try:
            client = self.client_factory()
            recent_connections = client.get_recent_connections(
                max_results=1000,
                since_ms=since_ms,
            )
        except Exception as error:
            raise AcceptanceCheckError(
                str(error) or "LinkedIn connections could not be checked."
            ) from error

        connected_by_public_id = {
            connection.get("public_id", "").casefold(): connection
            for connection in recent_connections
            if connection.get("public_id")
        }
        accepted_count = 0
        for connection_request in sent_requests:
            connection_request.checked_at = checked_at
            connection = connected_by_public_id.get(
                connection_request.public_id.casefold()
            )
            if connection:
                connected_at = connection.get("connected_at")
                connection_request.status = ConnectionRequest.Status.ACCEPTED
                connection_request.accepted_at = (
                    datetime.fromtimestamp(
                        connected_at / 1000,
                        tz=datetime_timezone.utc,
                    )
                    if isinstance(connected_at, int)
                    else checked_at
                )
                accepted_count += 1

        ConnectionRequest.objects.bulk_update(
            sent_requests,
            ["status", "accepted_at", "checked_at"],
        )
        return {
            "checked_count": len(sent_requests),
            "accepted_count": accepted_count,
            "pending_count": len(sent_requests) - accepted_count,
            "checked_at": checked_at.isoformat(),
        }

    def _check_and_send_requests(self, import_id: str, request_ids: list[int]) -> None:
        close_old_connections()
        try:
            client = self.client_factory()
            pending_public_ids = client.get_sent_invitation_public_ids()
        except (Exception, SystemExit):
            self._fail_remaining(import_id, "LinkedIn status could not be checked.")
            return

        for request_id in request_ids:
            connection_request = ConnectionRequest.objects.get(pk=request_id)
            connection_request.status = ConnectionRequest.Status.CHECKING
            connection_request.save(update_fields=["status"])

            checked_at = timezone.now()
            connection_request.provider_status = None
            if connection_request.public_id.casefold() in pending_public_ids:
                connection_request.status = ConnectionRequest.Status.PENDING
                connection_request.error = "Connection request is already pending."
            else:
                status_error = None
                try:
                    connection_state = client.get_connection_state(
                        connection_request.public_id,
                        name=connection_request.name,
                    )
                except Exception as error:
                    connection_state = "unknown"
                    status_error = error

                if connection_state == "connected":
                    connection_request.status = ConnectionRequest.Status.CONNECTED
                    connection_request.error = "Already connected."
                elif connection_state == "not_connected":
                    connection_request.status = ConnectionRequest.Status.READY
                    connection_request.error = ""
                else:
                    connection_request.status = ConnectionRequest.Status.FAILED
                    connection_request.error = (
                        str(status_error)
                        if status_error
                        else "Connection status could not be confirmed."
                    )
                    provider_status = getattr(status_error, "status", None)
                    if (
                        isinstance(provider_status, int)
                        and 100 <= provider_status <= 599
                    ):
                        connection_request.provider_status = provider_status

            connection_request.checked_at = checked_at
            connection_request.save(
                update_fields=["status", "error", "provider_status", "checked_at"]
            )

        eligible_ids = list(
            ConnectionRequest.objects.filter(
                id__in=request_ids,
                status=ConnectionRequest.Status.READY,
            ).values_list("id", flat=True)
        )
        ConnectionImport.objects.filter(pk=import_id).update(
            status=ConnectionImport.Status.SENDING
        )

        for request_id in eligible_ids:
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
                ConnectionRequest.Status.CHECKING,
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
        total_count = sum(
            person["status"] not in {"invalid", "duplicate"} for person in people
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
                person["status"] in {"invalid", "duplicate", "pending", "connected"}
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
