from django.db import migrations


STATUS_MAP = {
    "sent": "pending",
    "pending": "pending",
    "accepted": "accepted",
    "connected": "already_connected",
    "failed": "failed",
    "sending": "needs_review",
    "checking": "needs_review",
}

STATUS_PRIORITY = {
    "queued": 0,
    "failed": 1,
    "needs_review": 2,
    "pending": 3,
    "already_connected": 4,
    "accepted": 5,
}


def backfill_people_and_invitations(apps, schema_editor):
    ConnectionRequest = apps.get_model("login_api", "ConnectionRequest")
    Invitation = apps.get_model("login_api", "Invitation")
    Person = apps.get_model("login_api", "Person")

    rows = ConnectionRequest.objects.select_related("connection_import").order_by("id")
    for row in rows.iterator():
        normalized_public_id = row.public_id.strip().casefold()
        if not normalized_public_id:
            continue

        person, created = Person.objects.get_or_create(
            normalized_public_id=normalized_public_id,
            defaults={
                "name": row.name,
                "linkedin_url": row.linkedin_url,
                "public_id": row.public_id,
            },
        )
        if not created:
            updates = []
            if row.name and person.name != row.name:
                person.name = row.name
                updates.append("name")
            if row.linkedin_url and person.linkedin_url != row.linkedin_url:
                person.linkedin_url = row.linkedin_url
                updates.append("linkedin_url")
            if updates:
                person.save(update_fields=updates)

        row.person_id = person.id
        mapped_status = STATUS_MAP.get(row.status)
        if (
            mapped_status is None
            and row.status == "ready"
            and row.connection_import.status != "awaiting_approval"
        ):
            mapped_status = "needs_review"

        if mapped_status is not None:
            invitation, invitation_created = Invitation.objects.get_or_create(
                person_id=person.id,
                defaults={
                    "status": mapped_status,
                    "error": row.error,
                    "provider_status": row.provider_status,
                    "queued_at": row.connection_import.approved_at,
                    "sent_at": row.sent_at,
                    "accepted_at": row.accepted_at,
                    "checked_at": row.checked_at,
                },
            )
            if not invitation_created and STATUS_PRIORITY[mapped_status] >= STATUS_PRIORITY[invitation.status]:
                invitation.status = mapped_status
                invitation.error = row.error
                invitation.provider_status = row.provider_status
                invitation.queued_at = invitation.queued_at or row.connection_import.approved_at
                invitation.sent_at = invitation.sent_at or row.sent_at
                invitation.accepted_at = invitation.accepted_at or row.accepted_at
                invitation.checked_at = row.checked_at or invitation.checked_at
                invitation.save(
                    update_fields=[
                        "status",
                        "error",
                        "provider_status",
                        "queued_at",
                        "sent_at",
                        "accepted_at",
                        "checked_at",
                    ]
                )
            row.invitation_id = invitation.id

        row.save(update_fields=["person", "invitation"])


class Migration(migrations.Migration):
    dependencies = [
        ("login_api", "0004_invitation_messagetemplate_person_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_people_and_invitations, migrations.RunPython.noop),
    ]
