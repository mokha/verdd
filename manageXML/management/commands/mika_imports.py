from django.core.management.base import BaseCommand, CommandError
from ._private import *
from mikatools import *


def add_termwiki(json_file):
    term_json = json_load(script_path(json_file))
    for termwiki in term_json:
        sms_data = termwiki["sms"]
        for word in sms_data:
            print(word["word"])
            try:
                ls = Lexeme.objects.filter(lexeme=word["word"], language="sms")
                for l in ls:
                    a, created = Affiliation.objects.get_or_create(lexeme=l, title=word["word"], link=word["url"],
                                                                   checked=word["sanctioned"], type=TERMWIKI)
                    print(l)
            except Exception as e:
                print(e)


def add_deriv(json_file):
    deriv_json = json_load(script_path(json_file))
    for word1, derv_data in deriv_json.items():
        id, word = word1.split("_")
        try:
            l1 = Lexeme.objects.get(id=id, language="sms")
            for derivation in derv_data:
                l2 = Lexeme.objects.get(id=derivation[0].split("_")[0], language="sms")
                if "+Cmp" in derivation[1]:
                    rel_type = 2
                else:
                    rel_type = 3
                print(l1)
                print(l2)
                r, c = Relation.objects.get_or_create(type=rel_type, lexeme_from_id=l2.id, lexeme_to_id=l1.id,
                                                      notes=derivation[1])
        except Exception as e:
            print(e)


class Command(BaseCommand):
    '''
    Example: python manage.py import_csv -f ../data/Suomi-koltansaame_sanakirja_v1991_30052013.csv -s fin -t sms -n smsfin2004 -d ';'
    '''

    help = 'This command imports a CSV file into the database to be edited.'

    def add_arguments(self, parser):
        parser.add_argument("-c", "--command", type=str, help="termwiki for termwiki import", default=None)
        parser.add_argument('-f', '--file', type=str, help='The JSON file to import.', )

    def handle(self, *args, **options):
        json_file = options['file']

        if options['command'] == "termwiki":
            print("termwiki import")
            add_termwiki(json_file)
        elif options['command'] == "derivations":
            print("derivation import")
            add_deriv(json_file)
