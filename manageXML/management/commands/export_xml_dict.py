from django.core.management.base import (BaseCommand, CommandError)


def export(directory_path):
    pass


class Command(BaseCommand):
    '''
    This function generates the XML following the format in https://victorio.uit.no/langtech/trunk/words/dicts/finsms/
    The output is expected to be used in an online dictionary.
    Example: python manage.py export_xml_dict -d ../xml_src/
    '''

    help = 'Command to export an XML version of the dictionary.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory path where to store the XMLs in.', )

    def success_info(self, info):
        return self.stdout.write(self.style.SUCCESS(info))

    def error_info(self, info):
        return self.stdout.write(self.style.ERROR(info))

    def handle(self, *args, **options):
        directory_path = options['dir']
        export(directory_path)
