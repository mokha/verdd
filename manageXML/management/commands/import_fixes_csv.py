import django
from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from ._private import *
from collections import defaultdict
from operator import itemgetter
from manageXML.models import *
from manageXML.constants import VARIATION, TRANSLATION
from datetime import datetime
import logging
from copy import deepcopy
from django.conf import settings

logger = logging.getLogger('verdd')  # Get an instance of a logger


def log_change(lexeme_id, lexeme, edit, note):
    logger.info(
        "%s (%d): [%s] %s on %s" % (lexeme, lexeme_id, edit, note, datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)"))
    )  # edit, note time


def process(rows):
    # Assumptions:
    # -) lexemes don't have any homonyms

    existing_lexemes = defaultdict(list)  # correct -> all_wrong

    # ROWS format: ID, LANG, NEW REP, VARIATIONS
    rows.sort(key=itemgetter(1))  # sort rows by language
    for row in rows:  # fix encoding
        row[2] = fix_encoding(row[2])
        row[3:] = [fix_encoding(w) for w in row[3:]]

    # add lexemes that don't exist
    for row in rows:
        id = int(row[0])  # the id of the original lexeme
        # get original lexeme
        original_lexeme = Lexeme.objects.get(pk=id)  # get original lexeme
        pos = original_lexeme.pos
        language = original_lexeme.language
        homoId = original_lexeme.homoId
        df = original_lexeme.imported_from
        old_lexeme = original_lexeme.lexeme

        if not pos.strip():
            # check if lexeme already exists with pos
            try:
                l = Lexeme.objects.get(lexeme=row[2], language=language, pos__gt='', homoId=homoId)
                pos = l.pos
                original_lexeme.pos = l.pos
            except:
                pass

        original_lexeme.lexeme = row[2]
        main_lexeme = original_lexeme

        try:
            original_lexeme.save()  # try to fix the new changes
            log_change(original_lexeme.id, original_lexeme.lexeme, "UPDATE_LEX",
                       "Changed %s to %s" % (old_lexeme, original_lexeme.lexeme))
        except django.db.utils.IntegrityError as e:  # the lexeme already exists
            l = Lexeme.objects.get(lexeme=row[2], language=language, pos=pos, homoId=homoId)
            log_change(original_lexeme.id, original_lexeme.lexeme, "NA_LEX",
                       "Cannot edit, lexeme already exist with id %d" % l.id)
            existing_lexemes[l.id].append(original_lexeme.id)
            main_lexeme = l

        for w in row[3:]:
            try:
                _l = Lexeme.objects.get(lexeme=w, pos=pos, language=language, homoId=homoId)
                log_change(_l.id, _l.lexeme, "NA_LEX", "Lexeme already exist")
            except:
                _l = create_lexeme(lexeme=w,
                                   pos=pos,
                                   language=language,
                                   imported_from=df)
                title = _l.find_akusanat_affiliation()
                if title:
                    a, created = Affiliation.objects.get_or_create(lexeme=_l, title=title, type=AKUSANAT,
                                                                   link="{}{}".format(settings.WIKI_URL, title))
                log_change(_l.id, _l.lexeme, "CREATE_LEX",
                           "Created lexeme %s" % (_l.lexeme))

            r, created = Relation.objects.get_or_create(lexeme_from=main_lexeme, lexeme_to=_l, type=VARIATION,
                                                        notes="Imported from var/fixes by Jack")
            log_change(_l.id, _l.lexeme, "CREATE_VAR_RELATION",
                       "Created a relation between %s -> %s" % (main_lexeme.lexeme, _l.lexeme))

    for main_id, wrong_lexemes_ids in existing_lexemes.items():
        main_l = Lexeme.objects.get(pk=main_id)
        for wrong_id in wrong_lexemes_ids:
            wrong_l = Lexeme.objects.get(pk=wrong_id)
            relations = wrong_l.get_relations()
            for r in relations:
                # from Finnish
                if main_l.language == 'fin':
                    _r, created = Relation.objects.get_or_create(lexeme_from=main_l, lexeme_to=r.lexeme_to,
                                                                 type=TRANSLATION)
                else:
                    _r, created = Relation.objects.get_or_create(lexeme_from=r.lexeme_from, lexeme_to=main_l,
                                                                 type=TRANSLATION)
                if created:
                    log_change(main_l.id, main_l.lexeme, "CREATED_TRANSLATION",
                               "Created translation: %s -> %s" % (r.lexeme_from.lexeme, main_l.lexeme))
                if r.notes:
                    _r.notes = _r.notes + '\n' + r.notes if _r.notes else r.notes
                    _r.save()
                    log_change(_r.id, main_l.lexeme, "UPDATED_TRANSLATION",
                               "Updated notes of translation")

                existing_sources = [s.name for s in _r.source_set.all()]

                for s in r.source_set.all():
                    if s.name in existing_sources:
                        continue
                    _s = deepcopy(s)
                    _s.id = None
                    _s.relation = _r
                    _s.save()
            log_change(wrong_l.id, wrong_l.lexeme, "DELETED_LEX",
                       "Deleted lexeme: %s" % (wrong_l.lexeme))
            wrong_l.delete()  # delete


class Command(BaseCommand):
    '''
    Example: python manage.py import_fixes_csv -f ../data/lexemes-not-lexemes_2019-09-25_reduced_02.tsv -d '\t'
    '''

    help = 'This command imports a CSV file into the database by updating existing lexemes and adding new ones.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The CSV file to import.', )
        parser.add_argument('-d', '--delimiter', type=str, nargs='?', default=';',
                            help='The delimiter to use when reading the CSV file.', )

    def handle(self, *args, **options):
        file_path = options['file']
        d = options['delimiter']

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, 'r', encoding='utf-8') as fp:
            reader = csv.reader(fp, delimiter=d)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            process(rows)

        self.stdout.write(self.style.SUCCESS('Successfully imported the file "%s"' % (file_path,)))
