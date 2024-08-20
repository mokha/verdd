from uralicNLP import uralicApi
from mikatools import *


def get_lemmas():
    csv = open_read("2020-05-15T18_02_07-export.csv")
    csv.readline()
    lemmas = [x.split(",")[2] for x in csv]
    return lemmas


adjective_map = {}
ambiguous_adj_map = {}

for lemma in get_lemmas():
    morphs = uralicApi.analyze(lemma, "sms")
    lemmas = []
    for morph in morphs:
        morph = morph[0]
        if "+A+Attr" in morph:
            l = morph.split("+")[0]
            if l != lemma:
                lemmas.append(l)
    lemmas = list(set(lemmas))
    if len(lemmas) == 1:
        adjective_map[lemma] = lemmas[0]
    elif len(lemmas) > 1:
        ambiguous_adj_map[lemma] = lemmas

json_dump(adjective_map, "A_attr_to_A.json")
json_dump(ambiguous_adj_map, "A_attr_to_A_for_Jack.json")
