from manageXML.models import *
from collections import defaultdict
import xml.etree.ElementTree as ET
from uralicNLP import uralicApi
from wiki.semantic_api import SemanticAPI
import io

semAPI = SemanticAPI()

new_xml = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
pos_files = defaultdict(list)


def analyze(word, lang):
    try:
        a = uralicApi.analyze(word, lang)
        a = map(lambda r: r[0].split("+"), a)
        a = list(filter(lambda r: r[0] == word, a))
        if not a:
            return [[None]]
        a = list(map(lambda r: r[1:], a))
        a = list(filter(lambda r: r, a))
        return a
    except:
        pass
    return [[None]]


def query_semantic_search(lexeme, lang):
    r1 = semAPI.ask(
        query=(
            "[[%s:%s]]" % (lang.capitalize(), lexeme),
            "?Category",
            "?POS",
            "?Lang",
            "?Contlex",
        )
    )

    if "query" not in r1 or "results" not in r1["query"] or not r1["query"]["results"]:
        return (None,) * 4

    title, info = r1["query"]["results"].popitem()
    info = info["printouts"]
    pos = info["POS"][0]["fulltext"]
    contlex = [i["fulltext"] for i in info["Contlex"]]  # using the first contlex
    return title, info, pos, contlex


def parseXML(filename, lang="fin"):
    with io.open(filename, "r", encoding="utf-8") as fp:
        tree = ET.parse(fp)
        root = tree.getroot()
        namespaces = {"xml": "http://www.w3.org/XML/1998/namespace"}
        for e in root.findall("e"):
            map_e = e.find("map")
            sml_true = (
                True if (map_e is not None and "sml_ids" in map_e.attrib) else False
            )

            book_sources = e.findall("sources/book")
            sjm_source = [
                True if "name" in b.attrib and b.attrib["name"] == "sjm" else False
                for b in book_sources
            ]
            if not sml_true and not any(sjm_source):
                continue

            for l in e.find("lg").findall("l"):
                if not l.text:
                    continue
                context = e.find("lg/stg/st")
                tg = e.find('mg/tg[@xml:lang="' + lang + '"]', namespaces)
                if not tg:
                    continue
                for t in tg.findall("t"):
                    if not t.text:
                        continue

                    context_text = (
                        context.attrib["Contlex"]
                        if context is not None and "Contlex" in context.attrib
                        else l.attrib["pos"] + "_"
                    )
                    new_xml[t.text]["tg"][l.text] = {
                        **l.attrib,
                        "Contlex": context_text,
                    }
                    new_xml[t.text]["attributes"] = t.attrib

                    POS_pred = (
                        t.attrib["pos"]
                        if "pos" in t.attrib and t.attrib["pos"]
                        else l.attrib["pos"]
                    )
                    POS_pred = POS_pred if ":" not in POS_pred else "MWE"
                    pos_files[POS_pred].append(t.text)


def create_lexeme(**args):
    data = args.copy()
    data.pop("lexeme", None)
    data.pop("pos", None)
    data.pop("language", None)
    data.pop("homoId", None)

    l, created = Lexeme.objects.get_or_create(
        lexeme=args["lexeme"],
        pos=args["pos"],
        language=args["language"],
        homoId=args["homoId"] if "homoId" in args else 0,
        defaults=data,
    )
    return l


def create_relation(l1, l2, notes, source, source_type="book"):
    r, created = Relation.objects.get_or_create(
        lexeme_from=l1, lexeme_to=l2, type=0, defaults={"notes": notes}
    )
    s, created = Source.objects.get_or_create(
        relation=r, name=source, defaults={"type": source_type}
    )
    return r


def fix_encoding(text):
    # wrong -> correct
    encodings_map = {
        "ð": "đ",
        "ä": "ä",
        "Ä": "Ä",
        "Ö": "Ö",
        "ö̈": "ö",
        "â": "â",
        "Â": "Â",
        "å": "å",
        "Å": "Å",
        "õ": "õ",
        "Õ": "Õ",
        "č": "č",
        "Č": "Č",
        "ǯ": "ǯ",
        "Ǯ": "Ǯ",
        "ǧ": "ǧ",
        "Ǧ": "Ǧ",
        "ǩ": "ǩ",
        "Ǩ": "Ǩ",
        "š": "š",
        "Š": "Š",
        "ž": "ž",
        "Ž": "Ž",
        "ğ": "ǧ",
        "Ğ": "Ǧ",
        "Ẹ": "Ẹ",
        "ẹ": "ẹ",
        "a'": "aˈ",
        "ä'": "äˈ",
        "â'": "âˈ",
        "å'": "åˈ",
        "õ'": "õˈ",
        "i'": "iˈ",
        "e'": "eˈ",
        "u'": "uˈ",
        "y'": "yˈ",
        "ö'": "öˈ",
        "a´": "aˈ",
        "ä´": "äˈ",
        "â´": "âˈ",
        "å´": "åˈ",
        "õ´": "õˈ",
        "i´": "iˈ",
        "e´": "eˈ",
        "u´": "uˈ",
        "y´": "yˈ",
        "ö´": "öˈ",
        "a′": "aʹ",
        "ä′": "äʹ",
        "â′": "âʹ",
        "å′": "åʹ",
        "õ′": "õʹ",
        "i′": "iʹ",
        "e′": "eʹ",
        "u′": "uʹ",
        "y′": "yʹ",
        "ö′": "öʹ",
        "aˊ": "aʹ",
        "äˊ": "äʹ",
        "âˊ": "âʹ",
        "åˊ": "åʹ",
        "õˊ": "õʹ",
        "iˊ": "iʹ",
        "eˊ": "eʹ",
        "uˊ": "uʹ",
        "yˊ": "yʹ",
        "öˊ": "öʹ",
        "b´b": "bˈb",
        "c´c": "cˈc",
        "č´č": "čˈč",
        "ʒ´ʒ": "ʒˈʒ",
        "ǯ´ǯ": "ǯˈǯ",
        "d´d": "dˈd",
        "đ´đ": "đˈđ",
        "z´z": "zˈz",
        "ž´ž": "žˈž",
        "f´f": "fˈf",
        "g´g": "gˈg",
        "ǩ´ǩ": "ǩˈǩ",
        "ǥ´ǥ": "ǥˈǥ",
        "ǧ´ǧ": "ǧˈǧ",
        "ŋ´ŋ": "ŋˈŋ",
        "j´j": "jˈj",
        "k´k": "kˈk",
        "l´l": "lˈl",
        "m´m": "mˈm",
        "n´n": "nˈn",
        "p´p": "pˈp",
        "r´r": "rˈr",
        "s´s": "sˈs",
        "t´t": "tˈt",
        "v´v": "vˈv",
        "b'b": "bˈb",
        "c'c": "cˈc",
        "č'č": "čˈč",
        "ʒ'ʒ": "ʒˈʒ",
        "ǯ'ǯ": "ǯˈǯ",
        "d'd": "dˈd",
        "đ'đ": "đˈđ",
        "z'z": "zˈz",
        "ž'ž": "žˈž",
        "f'f": "fˈf",
        "g'g": "gˈg",
        "ǩ'ǩ": "ǩˈǩ",
        "ǥ'ǥ": "ǥˈǥ",
        "ǧ'ǧ": "ǧˈǧ",
        "ŋ'ŋ": "ŋˈŋ",
        "j'j": "jˈj",
        "k'k": "kˈk",
        "l'l": "lˈl",
        "m'm": "mˈm",
        "n'n": "nˈn",
        "p'p": "pˈp",
        "r'r": "rˈr",
        "s's": "sˈs",
        "t't": "tˈt",
        "v'v": "vˈv",
        "b’": "bˈ",
        "c’": "cˈ",
        "č’": "čˈ",
        "ʒ’": "ʒˈ",
        "ǯ’": "ǯˈ",
        "d’": "dˈ",
        "đ’": "đˈ",
        "z’": "zˈ",
        "ž’": "žˈ",
        "f’": "fˈ",
        "g’": "gˈ",
        "ǩ’": "ǩˈ",
        "ǥ’": "ǥˈ",
        "ǧ’": "ǧˈ",
        "ŋ’": "ŋˈ",
        "j’": "jˈ",
        "k’": "kˈ",
        "l’": "lˈ",
        "m’": "mˈ",
        "n’": "nˈ",
        "p’": "pˈ",
        "r’": "rˈ",
        "s’": "sˈ",
        "t’": "tˈ",
        "v’": "vˈ",
        "b´": "bˈ",
        "c´": "cˈ",
        "č´": "čˈ",
        "ʒ´": "ʒˈ",
        "ǯ´": "ǯˈ",
        "d´": "dˈ",
        "đ´": "đˈ",
        "z´": "zˈ",
        "ž´": "žˈ",
        "f´": "fˈ",
        "g´": "gˈ",
        "ǩ´": "ǩˈ",
        "ǥ´": "ǥˈ",
        "ǧ´": "ǧˈ",
        "ŋ´": "ŋˈ",
        "j´": "jˈ",
        "k´": "kˈ",
        "l´": "lˈ",
        "m´": "mˈ",
        "n´": "nˈ",
        "p´": "pˈ",
        "r´": "rˈ",
        "s´": "sˈ",
        "t´": "tˈ",
        "v´": "vˈ",
    }

    for wrong_enc, correct_enc in encodings_map.items():
        text = text.replace(wrong_enc, correct_enc)
    return text
