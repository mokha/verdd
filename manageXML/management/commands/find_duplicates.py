from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from manageXML.models import *
from manageXML.utils import get_duplicate_objects, obj_to_txt
from django.apps import apps


class Command(BaseCommand):
    """
    This command finds all duplicate items and prints them.

    Usage: python manage.py find_duplicates -m manageXML.Lexeme -d ; --unique lexeme language --fields id lexeme language pos

    """

    help = 'This command finds all duplicate items and prints them.'

    def add_arguments(self, parser):
        parser.add_argument('-m', '--model', type=str, help='The model to search for duplicates in. '
                                                            'Format: app.model (e.g. manageXML.Lexeme).', )
        parser.add_argument('-d', '--delimiter', type=str, nargs='?', default=';',
                            help='The delimiter to use when joining fields of duplicate objects.', )
        parser.add_argument('--unique', type=str, nargs='+', help='The unique field names to find duplicates in.')
        parser.add_argument('--fields', type=str, nargs='+', default=('id',), help='Fields to display.')

    def handle(self, *args, **options):
        try:
            app_name, model_name = options['model'].split('.')
            delimiter = options['delimiter']
            unique_fields = tuple(options['unique'])
            fields = tuple(options['fields'])

            _model = apps.get_model(app_name, model_name)

            duplicates = get_duplicate_objects(model=_model, unique_fields=unique_fields)

            output = []
            for dd in duplicates:  # for each duplicate values
                dup_line = []
                for _d in _model.objects.filter(**{x: dd[x] for x in unique_fields}):  # get the objects that have them
                    dup_line.append(obj_to_txt(_d, fields=fields, delimiter=delimiter))  # convert them to text
                output.append(delimiter.join(dup_line))  # add duplicate line

            self.stdout.write("\n".join(output))  # print final result
        except Exception as e:
            self.stderr.write(self.style.ERROR(str(e)))
