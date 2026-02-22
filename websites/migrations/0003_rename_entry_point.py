from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('websites', '0002_website_entry_point'),
    ]

    operations = [
        migrations.RenameField(
            model_name='website',
            old_name='entry_point',
            new_name='siliconfriendly_entry_point',
        ),
    ]
