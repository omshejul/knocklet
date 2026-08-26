import uuid

from django.db import models


class ConnectionImport(models.Model):
    class Status(models.TextChoices):
        AWAITING_APPROVAL = "awaiting_approval", "Awaiting approval"
        CHECKING = "checking", "Checking"
        SENDING = "sending", "Sending"
        COMPLETE = "complete", "Complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.AWAITING_APPROVAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    message_template = models.ForeignKey(
        "MessageTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="connection_imports",
    )
    auto_message_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class ConnectionRequest(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Ready"
        INVALID = "invalid", "Invalid"
        DUPLICATE = "duplicate", "Duplicate"
        SKIPPED = "skipped", "Skipped"
        CHECKING = "checking", "Checking"
        PENDING = "pending", "Pending"
        CONNECTED = "connected", "Connected"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        ACCEPTED = "accepted", "Accepted"

    connection_import = models.ForeignKey(
        ConnectionImport,
        on_delete=models.CASCADE,
        related_name="requests",
    )
    row_number = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    linkedin_url = models.URLField(max_length=500, blank=True)
    public_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    error = models.TextField(blank=True)
    provider_status = models.PositiveSmallIntegerField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    person = models.ForeignKey(
        "Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_rows",
    )
    invitation = models.ForeignKey(
        "Invitation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_rows",
    )

    class Meta:
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection_import", "row_number"],
                name="unique_request_row_per_import",
            )
        ]


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    linkedin_url = models.URLField(max_length=500, blank=True)
    public_id = models.CharField(max_length=255)
    normalized_public_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "normalized_public_id"]

    def save(self, *args, **kwargs):
        self.normalized_public_id = self.public_id.strip().casefold()
        super().save(*args, **kwargs)


class Invitation(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        CHECKING = "checking", "Checking"
        SENDING = "sending", "Sending"
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        ALREADY_CONNECTED = "already_connected", "Already connected"
        FAILED = "failed", "Failed"
        NEEDS_REVIEW = "needs_review", "Needs review"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        related_name="invitation",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    error = models.TextField(blank=True)
    provider_status = models.PositiveSmallIntegerField(null=True, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class MessageTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default="Follow-up")
    body = models.TextField()
    is_active = models.BooleanField(default=False)
    auto_send_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class Message(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        NEEDS_REVIEW = "needs_review", "Needs review"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.OneToOneField(
        Invitation,
        on_delete=models.CASCADE,
        related_name="message",
    )
    template = models.ForeignKey(
        MessageTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    body = models.TextField()
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    error = models.TextField(blank=True)
    provider_status = models.PositiveSmallIntegerField(null=True, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class WorkItem(models.Model):
    class Kind(models.TextChoices):
        SEND_INVITATION = "send_invitation", "Send invitation"
        CHECK_ACCEPTANCES = "check_acceptances", "Check acceptances"
        SEND_MESSAGE = "send_message", "Send message"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        NEEDS_REVIEW = "needs_review", "Needs review"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    invitation = models.ForeignKey(
        Invitation,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="work_items",
    )
    message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="work_items",
    )
    dedupe_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    due_at = models.DateTimeField()
    attempt_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    provider_status = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_at", "created_at"]
        indexes = [models.Index(fields=["status", "due_at"])]
