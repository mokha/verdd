from django.core.management.base import BaseCommand, CommandError
from manageXML.models import *
from tqdm import tqdm

class Command(BaseCommand):
    '''
    Example: python manage.py save_all_lexemes
    '''

    help = 'This command calls the save function to update all lexemes. Used when a new field is added to the database.'

    def handle(self, *args, **options):
        all_l = Lexeme.objects.all()
        for l in tqdm(all_l):
            l.save()

        self.stdout.write(self.style.SUCCESS('Successfully saved %d lexemes' % (len(all_l),)))
