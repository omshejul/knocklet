from django.db import migrations, models


FIRST_NAME_PREFIXES = {
    "adv",
    "ca",
    "cma",
    "cpa",
    "cs",
    "dr",
    "mr",
    "mrs",
    "ms",
    "prof",
}


def backfill_first_names(apps, schema_editor):
    Person = apps.get_model("login_api", "Person")
    for person in Person.objects.all().iterator():
        name_parts = person.name.strip().split()
        while (
            len(name_parts) > 1
            and name_parts[0].rstrip(".").casefold() in FIRST_NAME_PREFIXES
        ):
            name_parts.pop(0)
        person.first_name = name_parts[0] if name_parts else ""
        person.save(update_fields=["first_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("login_api", "0007_single_template_delay"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="first_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(backfill_first_names, migrations.RunPython.noop),
    ]
