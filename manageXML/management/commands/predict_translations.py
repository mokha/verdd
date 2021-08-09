from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from django.db.models import *
from django.db.models.functions import *
from manageXML.utils import get_duplicate_objects, annotate_objects, obj_to_txt
from django.apps import apps
import ast
from django.db.models import Prefetch, F, Value, When, Case, Q
import csv, io
from manageXML.models import *
from distutils.util import strtobool
import networkx as nx
from networkx import *
import io, csv, time, uuid
from tqdm import tqdm


def predict(src_lang, tgt_lang, approved=None):
    src_lexemes = Lexeme.objects.filter(language=src_lang, checked=approved) \
        .values_list('id', 'lexeme', 'pos', 'homoId').all()
    tgt_lexemes = Lexeme.objects.filter(language=tgt_lang, checked=approved) \
        .values_list('id', 'lexeme', 'pos', 'homoId').all()

    relations = Relation.objects.prefetch_related(Prefetch('lexeme_from'), Prefetch('lexeme_to')) \
        .filter(type=TRANSLATION) \
        .filter(
        Q(lexeme_from__language=src_lang) | Q(lexeme_from__language=tgt_lang) |
        Q(lexeme_to__language=src_lang) | Q(lexeme_to__language=tgt_lang)
    ).all()

    src_ids = dict([(_l[0], _l) for _l in src_lexemes])
    tgt_ids = dict([(_l[0], _l) for _l in tgt_lexemes])
    all_nodes = {**src_ids, **tgt_ids}

    G = nx.Graph()

    for r in tqdm(relations):
        G.add_node(r.lexeme_from.id)
        G.add_node(r.lexeme_to.id)
        G.add_edge(r.lexeme_from.id, r.lexeme_to.id)

    to_predict = []
    for node in src_ids:
        if not G.has_node(node):
            continue

        for n in G.neighbors(node):
            for _n in G.neighbors(n):
                if _n in tgt_ids:
                    to_predict.append((node, _n))

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
        parser.add_argument('-d', '--dir', type=str, help='The directory path where to store the CSV file in.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('--approved', type=lambda v: bool(strtobool(v)), nargs='?', const=True, default=None, )

    def handle(self, *args, **options):
        try:
            preds = predict(src_lang=options['source'], tgt_lang=options['target'],
                            approved=options.get('approved', None))

            _filename = "{}-{}-predictions-{}-{}.csv".format(
                options['source'],
                options['target'],
                time.strftime("%Y%m%d-%H%M%S"),
                str(uuid.uuid4())[:5]
            )
            with io.open("{}/{}".format(options['dir'], _filename), 'w', encoding='utf-8') as f:
                for u, v, p in preds:
                    f.write("\t".join(u + v + (str(p),)))
        except Exception as e:
            self.stderr.write(self.style.ERROR(str(e)))
