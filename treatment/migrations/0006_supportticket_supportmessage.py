from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('treatment', '0005_sitesettings_delete_exerciseprocessing'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=200)),
                ('status', models.CharField(
                    choices=[('open', 'Ouvert'), ('in_progress', 'En cours'), ('closed', 'Fermé')],
                    default='open',
                    max_length=20,
                )),
                ('is_priority', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='support_tickets',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Ticket support',
                'verbose_name_plural': 'Tickets support',
                'ordering': ['-is_priority', '-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SupportMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender_type', models.CharField(
                    choices=[('user', 'Utilisateur'), ('admin', 'Support')],
                    max_length=10,
                )),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='treatment.supportticket',
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
