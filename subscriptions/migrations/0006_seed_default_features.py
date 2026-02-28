from django.db import migrations


DEFAULT_FEATURES = [
    {
        'key': 'history_days',
        'label': 'Durée de l\'historique',
        'description': 'Nombre de jours pendant lesquels les corrections sont accessibles (0 = illimité).',
        'feature_type': 'integer',
        'default_value': '30',
    },
    {
        'key': 'priority_support',
        'label': 'Support prioritaire',
        'description': 'Le support répond en priorité aux utilisateurs disposant de cette fonctionnalité.',
        'feature_type': 'boolean',
        'default_value': 'false',
    },
    {
        'key': 'export_pdf',
        'label': 'Export PDF des corrections',
        'description': 'Permet de télécharger les corrections au format PDF.',
        'feature_type': 'boolean',
        'default_value': 'false',
    },
    {
        'key': 'advanced_subjects',
        'label': 'Accès aux matières avancées',
        'description': 'Autorise les corrections sur les matières avancées (Physique, Chimie, Maths Sup…).',
        'feature_type': 'boolean',
        'default_value': 'false',
    },
]


def seed_features(apps, schema_editor):
    Feature = apps.get_model('subscriptions', 'Feature')
    for f in DEFAULT_FEATURES:
        Feature.objects.get_or_create(key=f['key'], defaults=f)


def reverse_seed(apps, schema_editor):
    Feature = apps.get_model('subscriptions', 'Feature')
    Feature.objects.filter(key__in=[f['key'] for f in DEFAULT_FEATURES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0005_add_feature_packfeature'),
    ]

    operations = [
        migrations.RunPython(seed_features, reverse_seed),
    ]
