import csv
import io
import threading
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import unquote, urlparse
from uuid import uuid4


MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 100


class CsvImportError(ValueError):
    pass


class ImportNotFound(Exception):
    pass


class ImportConflict(Exception):
    pass


@dataclass
class ImportedPerson:
    row_number: int
    name: str
    linkedin_url: str
    public_id: str
    status: str
    error: str | None = None


@dataclass
class ConnectionImport:
    id: str
    filename: str
    people: list[ImportedPerson]
    status: str = "awaiting_approval"
    created_at: str = field(default_factory=lambda: _now())
    completed_at: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def parse_clay_csv(data: bytes, filename: str) -> ConnectionImport:
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

    people: list[ImportedPerson] = []
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
                ImportedPerson(
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
                ImportedPerson(
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
            ImportedPerson(
                row_number=row_number,
                name=full_name or public_id,
                linkedin_url=linkedin_url,
                public_id=public_id,
                status="ready",
            )
        )

    if not people:
        raise CsvImportError("CSV has no people.")

    return ConnectionImport(id=str(uuid4()), filename=filename, people=people)


ClientFactory = Callable[[], object]


class ConnectionImportStore:
    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self.client_factory = client_factory or self._get_client
        self._imports: dict[str, ConnectionImport] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _get_client():
        from auth import get_client

        return get_client()

    def create(self, data: bytes, filename: str) -> dict:
        connection_import = parse_clay_csv(data, filename)
        with self._lock:
            self._imports[connection_import.id] = connection_import
        return self._snapshot(connection_import)

    def get(self, import_id: str) -> dict:
        with self._lock:
            connection_import = self._imports.get(import_id)
            if connection_import is None:
                raise ImportNotFound
            return self._snapshot(connection_import)

    def approve(self, import_id: str) -> dict:
        with self._lock:
            connection_import = self._imports.get(import_id)
            if connection_import is None:
                raise ImportNotFound
            if connection_import.status != "awaiting_approval":
                raise ImportConflict
            if not any(person.status == "ready" for person in connection_import.people):
                raise ImportConflict

            connection_import.status = "sending"
            thread = threading.Thread(
                target=self._send_requests,
                args=(import_id,),
                daemon=True,
            )
            self._threads[import_id] = thread
            snapshot = self._snapshot(connection_import)

        thread.start()
        return snapshot

    def wait(self, import_id: str, timeout: float = 5) -> dict:
        thread = self._threads.get(import_id)
        if thread is not None:
            thread.join(timeout)
        return self.get(import_id)

    def _send_requests(self, import_id: str) -> None:
        try:
            client = self.client_factory()
        except BaseException:
            self._fail_remaining(import_id, "LinkedIn session could not be opened.")
            return

        with self._lock:
            ready_indexes = [
                index
                for index, person in enumerate(self._imports[import_id].people)
                if person.status == "ready"
            ]

        for index in ready_indexes:
            with self._lock:
                person = self._imports[import_id].people[index]
                person.status = "sending"
                public_id = person.public_id

            try:
                result = client.add_connection(profile_public_id=public_id)
                response_status = int((result or {}).get("status", 0))
                sent = 200 <= response_status < 300
                error = None if sent else f"LinkedIn returned status {response_status or 'unknown'}."
            except BaseException as request_error:
                sent = False
                error = str(request_error) or "Request failed."

            with self._lock:
                person = self._imports[import_id].people[index]
                person.status = "sent" if sent else "failed"
                person.error = error

        with self._lock:
            connection_import = self._imports[import_id]
            connection_import.status = "complete"
            connection_import.completed_at = _now()

    def _fail_remaining(self, import_id: str, error: str) -> None:
        with self._lock:
            connection_import = self._imports[import_id]
            for person in connection_import.people:
                if person.status == "ready":
                    person.status = "failed"
                    person.error = error
            connection_import.status = "complete"
            connection_import.completed_at = _now()

    @staticmethod
    def _snapshot(connection_import: ConnectionImport) -> dict:
        people = [asdict(person) for person in deepcopy(connection_import.people)]
        return {
            "id": connection_import.id,
            "filename": connection_import.filename,
            "status": connection_import.status,
            "people": people,
            "ready_count": sum(person["status"] == "ready" for person in people),
            "sent_count": sum(person["status"] == "sent" for person in people),
            "failed_count": sum(person["status"] == "failed" for person in people),
            "skipped_count": sum(
                person["status"] in {"invalid", "duplicate"} for person in people
            ),
            "created_at": connection_import.created_at,
            "completed_at": connection_import.completed_at,
        }
