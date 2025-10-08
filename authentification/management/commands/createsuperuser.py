from django.contrib.auth.management.commands import createsuperuser
from django.core.management import CommandError

class Command(createsuperuser.Command):
    help = 'Create a superuser with email as the username field'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        # Remplacer l'argument username par email
        parser.add_argument(
            '--email',
            dest='email',
            default=None,
            help='Specifies the email for the superuser.',
        )

    def handle(self, *args, **options):
        options.setdefault('email', options.get('username'))
        if not options['email']:
            raise CommandError("Vous devez spécifier un email avec --email.")
        # Supprimer username des options pour éviter l'erreur
        options['username'] = None
        # Appeler la méthode handle de la classe parent
        super().handle(*args, **options)