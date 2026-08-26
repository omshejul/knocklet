import re

from django.db import transaction

from .models import MessageTemplate

TEMPLATE_FIELD_PATTERN = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
TEMPLATE_FIELDS = {
    "first_name": "First name",
    "full_name": "Full name",
}
MAX_DELAY_MINUTES = 7 * 24 * 60


def get_active_template() -> dict | None:
    template = MessageTemplate.objects.filter(is_active=True).first()
    return template_snapshot(template) if template else None


def list_template_fields() -> list[dict]:
    return [
        {
            "name": name,
            "label": label,
            "placeholder": f"{{{name}}}",
        }
        for name, label in TEMPLATE_FIELDS.items()
    ]


def validate_template_body(body: str) -> None:
    placeholders = TEMPLATE_FIELD_PATTERN.findall(body)
    unknown = [name for name in placeholders if name not in TEMPLATE_FIELDS]
    if unknown:
        raise ValueError(f"Unknown message field: {{{unknown[0]}}}.")

    text_without_fields = TEMPLATE_FIELD_PATTERN.sub("", body)
    if "{" in text_without_fields or "}" in text_without_fields:
        raise ValueError("Message fields must be selected from the field menu.")


def render_template_body(body: str, full_name: str) -> str:
    validate_template_body(body)
    clean_name = full_name.strip()
    values = {
        "first_name": clean_name.split()[0] if clean_name else "there",
        "full_name": clean_name or "there",
    }
    return TEMPLATE_FIELD_PATTERN.sub(
        lambda match: values[match.group(1)],
        body,
    )


def validate_rendered_message_body(body: str) -> None:
    if "{" in body or "}" in body:
        raise ValueError("Message contains an unresolved field and was not sent.")


@transaction.atomic
def save_active_template(
    *,
    name: str,
    body: str,
    auto_send_enabled: bool,
    delay_minutes: int,
) -> dict:
    cleaned_body = body.strip()
    if not cleaned_body:
        raise ValueError("Message text is required.")
    validate_template_body(cleaned_body)
    if not 0 <= delay_minutes <= MAX_DELAY_MINUTES:
        raise ValueError("Delay must be between 0 and 10,080 minutes.")
    template = (
        MessageTemplate.objects.select_for_update().filter(is_active=True).first()
        or MessageTemplate.objects.select_for_update().first()
        or MessageTemplate()
    )
    if template.pk:
        MessageTemplate.objects.exclude(pk=template.pk).delete()
    template.name = name.strip() or "Follow-up"
    template.body = cleaned_body
    template.is_active = True
    template.auto_send_enabled = auto_send_enabled
    template.delay_minutes = delay_minutes
    template.save()
    return template_snapshot(template)


def template_snapshot(template: MessageTemplate) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "body": template.body,
        "is_active": template.is_active,
        "auto_send_enabled": template.auto_send_enabled,
        "delay_minutes": template.delay_minutes,
        "updated_at": template.updated_at.isoformat(),
    }
