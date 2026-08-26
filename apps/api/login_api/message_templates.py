from django.db import transaction

from .models import MessageTemplate


def get_active_template() -> dict | None:
    template = MessageTemplate.objects.filter(is_active=True).first()
    return template_snapshot(template) if template else None


@transaction.atomic
def save_active_template(
    *,
    name: str,
    body: str,
    auto_send_enabled: bool,
) -> dict:
    cleaned_body = body.strip()
    if not cleaned_body:
        raise ValueError("Message text is required.")
    MessageTemplate.objects.filter(is_active=True).update(is_active=False)
    template = MessageTemplate.objects.create(
        name=name.strip() or "Follow-up",
        body=cleaned_body,
        is_active=True,
        auto_send_enabled=auto_send_enabled,
    )
    return template_snapshot(template)


def template_snapshot(template: MessageTemplate) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "body": template.body,
        "is_active": template.is_active,
        "auto_send_enabled": template.auto_send_enabled,
        "updated_at": template.updated_at.isoformat(),
    }
