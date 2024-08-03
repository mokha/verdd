from mikatools import *
from uralicNLP import uralicApi


def list_not_in_fst():
    csv = open_read("/Users/mikahama/Downloads/2019-10-08T12_15_55-export.csv")
    csv.readline()
    r = []
    for l in csv:
        w = l.split(",")[2]
        a = uralicApi.analyze(w, "sms")
        if len(a) == 0:
            r.append(w)
    out = open_write("jackille_sms.txt")
    out.write("\n".join(r))
    out.close()


def _deriv_analysis(word, words):
    anas = uralicApi.analyze(word, "sms")
    deriv_lemmas = []
    for ana in anas:
        a = ana[0]
        if "+Der" in a:
            w = a.split("+")[0]
            if w is not word:
                w_i = get_id(w, words)
                deriv_lemmas.append([w_i + "_" + w, a])
    return deriv_lemmas


def get_id(word, words):
    for w in words:
        if w[1] == word:
            return w[0]
    else:
        return "XXX"


def list_deriv():
    csv = open_read("2019-10-08T12_15_55-export.csv")
    csv.readline()
    r = []
    words = []
    for l in csv:
        w = l.split(",")[2]
        i = l.split(",")[0]
        words.append((i, w))
    d_lem = {}
    for word in words:
        a = _deriv_analysis(word[1], words)
        if len(a) > 0:
            d_lem["_".join(word)] = a
    json_dump(d_lem, "sms_deriv.json")


list_deriv()
