from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch, F, Value, When, Case, Q
from manageXML.models import *
from distutils.util import strtobool
import networkx as nx
from networkx import *
import io, time, uuid
from tqdm import tqdm


def predict(src_lang, tgt_lang, approved=None):
    src_lexemes = Lexeme.objects.filter(language=src_lang) \
        .values('id', 'language', 'lexeme', 'pos', 'homoId').all()
    tgt_lexemes = Lexeme.objects.filter(language=tgt_lang) \
        .values('id', 'language', 'lexeme', 'pos', 'homoId').all()

    relations = Relation.objects.prefetch_related(Prefetch('lexeme_from'), Prefetch('lexeme_to')) \
        .filter(type=TRANSLATION) \
        .filter(
        Q(lexeme_from__language=src_lang) | Q(lexeme_from__language=tgt_lang) |
        Q(lexeme_to__language=src_lang) | Q(lexeme_to__language=tgt_lang)
    )
    if approved is not None:
        relations = relations.filter(checked=approved)

    relations = relations.all()

    existing_relations = Relation.objects.filter(type=TRANSLATION) \
        .filter(lexeme_from__language=src_lang, lexeme_to__language=tgt_lang) \
        .values_list('lexeme_from__id', 'lexeme_to__id')
    existing_relations = [(str(_er[0]), str(_er[1]),) for _er in existing_relations]

    src_ids = dict([(str(_l['id']), _l) for _l in src_lexemes])
    tgt_ids = dict([(str(_l['id']), _l) for _l in tgt_lexemes])
    all_nodes = {**src_ids, **tgt_ids}

    G = nx.Graph()

    for r in tqdm(relations):
        if not r.lexeme_from or not r.lexeme_to:
            continue
        G.add_node(str(r.lexeme_from.id))
        G.add_node(str(r.lexeme_to.id))
        G.add_edge(str(r.lexeme_from.id), str(r.lexeme_to.id))

    to_predict = []
    for node in src_ids:
        if not G.has_node(node):
            continue

        for n in G.neighbors(node):
            for _n in G.neighbors(n):
                if _n in tgt_ids:
                    to_predict.append((node, _n))
    to_predict = list(set(to_predict) - set(existing_relations))

    preds = jaccard_coefficient(G, to_predict)
    preds = list(set(preds))
    preds = [p for p in preds if p[2] > 0]
    preds = sorted(preds, key=lambda k: k[2], reverse=True)
    preds = [(all_nodes[p[0]], all_nodes[p[1]], p[2]) for p in preds]
    return preds


class Command(BaseCommand):
    """
    A script for predicting new translations using all the intermediate available translations as pivots.

    Usage: python manage.py predict_translations -s sms -t fin -d /tmp/ --approved

    """

    help = 'This command finds all duplicate items and prints them.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory path where to store the TSV file in.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('--approved', type=lambda v: bool(strtobool(v)), nargs='?', const=True, default=None, )

    def handle(self, *args, **options):
        try:
            preds = predict(src_lang=options['source'], tgt_lang=options['target'],
                            approved=options.get('approved', None))

            _filename = "{}-{}-predictions-{}-{}.tsv".format(
                options['source'],
                options['target'],
                time.strftime("%Y%m%d-%H%M%S"),
                str(uuid.uuid4())[:5]
            )
            output_path = "{}/{}".format(options['dir'], _filename)
            with io.open(output_path, 'w', encoding='utf-8') as f:
                lines = []
                for u, v, p in preds:
                    lines.append("\t".join([
                        str(u['id']), u['language'], u['lexeme'], u['pos'], str(u['homoId']),
                        str(v['id']), v['language'], v['lexeme'], v['pos'], str(v['homoId']),
                        str(p)
                    ]))
                f.write("\n".join(lines))
            self.stdout.write(
                self.style.SUCCESS('Successfully predicted translations into the file: {}.'.format(output_path)))
        except Exception as e:
            self.stderr.write(self.style.ERROR(str(e)))
