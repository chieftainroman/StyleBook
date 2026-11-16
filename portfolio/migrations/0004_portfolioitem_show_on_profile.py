from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0003_portfolioitem_fmt'),
    ]

    operations = [
        migrations.AddField(
            model_name='portfolioitem',
            name='show_on_profile',
            field=models.BooleanField(default=True),
        ),
    ]
