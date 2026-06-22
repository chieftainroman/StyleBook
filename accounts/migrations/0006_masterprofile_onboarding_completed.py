from django.db import migrations, models


def mark_complete_profiles_as_onboarded(apps, schema_editor):
    """
    Existing users with a 'complete' profile (specialty + location + years_exp + bio + phone)
    should not be forced into the wizard. Mark them as already onboarded.
    """
    MasterProfile = apps.get_model('accounts', 'MasterProfile')
    for p in MasterProfile.objects.all():
        if all([p.specialty, p.location, p.years_exp > 0, p.bio, p.phone]):
            p.onboarding_completed = True
            p.save(update_fields=['onboarding_completed'])


def reverse_noop(apps, schema_editor):
    """Reverse migration is a no-op — undoing wouldn't be meaningful."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_certificate_honor_workexperience'),
    ]

    operations = [
        migrations.AddField(
            model_name='masterprofile',
            name='onboarding_completed',
            field=models.BooleanField(default=False, help_text='True once the user has finished or explicitly skipped the wizard'),
        ),
        migrations.RunPython(mark_complete_profiles_as_onboarded, reverse_noop),
    ]