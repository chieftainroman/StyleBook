from django.db import migrations, models


def mark_existing_users_verified(apps, schema_editor):
    """Existing users get email_verified=True so banner doesn't bother them."""
    MasterProfile = apps.get_model('accounts', 'MasterProfile')
    MasterProfile.objects.update(email_verified=True)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_masterprofile_onboarding_completed'),
    ]

    operations = [
        migrations.AddField(
            model_name='masterprofile',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_users_verified, reverse_noop),
    ]