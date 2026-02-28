from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0004_transaction_payment_method_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=50, unique=True)),
                ('label', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('feature_type', models.CharField(
                    choices=[('boolean', 'Oui / Non'), ('integer', 'Nombre (jours, etc.)')],
                    default='boolean',
                    max_length=20,
                )),
                ('default_value', models.CharField(
                    default='false',
                    help_text="'true'/'false' pour boolean, nombre pour integer",
                    max_length=100,
                )),
            ],
            options={
                'verbose_name': 'Fonctionnalité',
                'verbose_name_plural': 'Fonctionnalités catalogue',
                'ordering': ['label'],
            },
        ),
        migrations.CreateModel(
            name='PackFeature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=100)),
                ('feature', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pack_features',
                    to='subscriptions.feature',
                )),
                ('pack', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pack_features',
                    to='subscriptions.pack',
                )),
            ],
            options={
                'verbose_name': 'Feature du pack',
                'verbose_name_plural': 'Features du pack',
                'unique_together': {('pack', 'feature')},
            },
        ),
    ]
