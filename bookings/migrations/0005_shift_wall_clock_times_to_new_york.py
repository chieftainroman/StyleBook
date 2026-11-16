"""
One-time data fix that goes with TIME_ZONE = 'America/New_York'.

Until now Django ran on its default zone, America/Chicago, so an appointment a
master set for 10:00 was saved as "10:00 Chicago". Read back in New York time
it would show as 11:00. This moves every APPOINTMENT time back one hour so it
reads 10:00 again. (New York is always exactly one hour ahead of Chicago, and
both change clocks for daylight saving on the same dates.)

Only times a person chose are shifted: booking start/end and one-off blocked
periods. Automatic timestamps (created_at, cancelled_at, code expiry) recorded
real moments in time, and they read correctly in New York time already.
"""
from django.db import migrations

FORWARD = """
UPDATE bookings_booking
   SET start_time = start_time - interval '1 hour',
       end_time   = end_time   - interval '1 hour';
UPDATE accounts_unavailableslot
   SET start_datetime = start_datetime - interval '1 hour',
       end_datetime   = end_datetime   - interval '1 hour'
 WHERE start_datetime IS NOT NULL;
"""

BACKWARD = FORWARD.replace("- interval", "+ interval")


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0004_alter_booking_source'),
        ('accounts', '0009_masterprofile_concurrent_clients_and_more'),
    ]

    operations = [
        migrations.RunSQL(FORWARD, reverse_sql=BACKWARD),
    ]
