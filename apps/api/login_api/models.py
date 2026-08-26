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

    class Meta:
        ordering = ["-created_at"]


class ConnectionRequest(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Ready"
        INVALID = "invalid", "Invalid"
        DUPLICATE = "duplicate", "Duplicate"
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

    class Meta:
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection_import", "row_number"],
                name="unique_request_row_per_import",
            )
        ]
