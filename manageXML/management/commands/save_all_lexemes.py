from django.core.management.base import BaseCommand, CommandError
from manageXML.models import *


class Command(BaseCommand):
    '''
    Example: python manage.py save_all_lexemes
    '''

    help = 'This command calls the save function to update all lexemes. Used when a new field is added to the database.'

    def handle(self, *args, **options):

        for l in Lexeme.objects.all():
            l.save()

        self.stdout.write(self.style.SUCCESS('Successfully imported the file "%s"' % (file_path,)))
