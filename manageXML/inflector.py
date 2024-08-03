# encoding: utf-8
import os
from uralicNLP import uralicApi
from django.conf import settings
from collections import defaultdict

try:
    import hfst
except:
    pass


class Inflector:
    def __init__(self):
        self._transducers_base_dir = settings.TRANSDUCERS_PATH

    def get_supported_languages(self):
        langs = []
        if self._transducers_base_dir:
            for x in os.listdir(self._transducers_base_dir):
                if os.path.isdir(os.path.join(self._transducers_base_dir, x)):
                    langs.append(x)
        return langs

    def return_model(self, language, model_type):
        if model_type == "analyser":
            filename = os.path.join(self._transducers_base_dir, language + "/analyser-gt-desc.hfstol")
        elif model_type == "analyser-norm":
            filename = os.path.join(self._transducers_base_dir, language + "/analyser-gt-norm.hfstol")
        elif model_type == "generator":
            filename = os.path.join(self._transducers_base_dir, language + "/generator-dict-gt-norm.hfstol")
        elif model_type == "generator-desc":
            filename = os.path.join(self._transducers_base_dir, language + "/generator-gt-desc.hfstol")
        elif model_type == "generator-norm":
            filename = os.path.join(self._transducers_base_dir, language + "/generator-gt-norm.hfstol")
        elif model_type == "metadata.json":
            filename = os.path.join(self._transducers_base_dir, language + "/metadata.json")
        else:
            filename = os.path.join(self._transducers_base_dir, language + "/disambiguator.cg3")
        return os.path.getsize(filename), open(filename, "rb")

    def return_all_analysis(self, word_form, language="sms"):
        filename = os.path.join(self._transducers_base_dir, language + "/analyser-gt-desc.hfstol")
        try:
            input_stream = hfst.HfstInputStream(filename)
            analyser = input_stream.read()
        except:
            return []
        analysis = analyser.lookup(word_form)
        return analysis

    def generate_form(self, hfst_query, language="sms"):
        filename = os.path.join(self._transducers_base_dir, language + "/generator-dict-gt-norm.hfstol")
        try:
            input_stream = hfst.HfstInputStream(filename)
            analyser = input_stream.read()
        except:
            return []
        analysis = analyser.lookup(hfst_query)
        return analysis

    def return_lemmas(self, word_form, language="sms"):
        analysis = self.return_all_analysis(word_form, language)
        lemmas = []
        for tupla in analysis:
            an = tupla[0]
            if "@" in an:
                lemma = an.split("@")[0]
            else:
                lemma = an
            if "+" in lemma:
                lemmas.append(lemma.split("+")[0])
        lemmas = list(set(lemmas))
        return lemmas

    def __inflect_sms__(self, lemma, pos):
        file_path = os.path.join(self._transducers_base_dir, "sms/generator-dict-gt-norm.hfstol")
        queries, q_trans = self.__generator_queries__(lemma, pos)
        return self.__inflect_generic__(queries, q_trans, file_path)

    def __add_lemma_to_queries__(self, lemma, queries):
        results = []
        for q in queries:
            results.append(lemma + "+" + q)
        return results

    def __get_trans__(self, key_list):
        trans = ""
        for item in key_list:
            trans = trans + self.human_readable[item] + " "
        return trans

    def __inflect_generic__(self, queries, q_translations, file_path):
        input_stream = hfst.HfstInputStream(file_path)
        synthetiser = input_stream.read()
        results = defaultdict(list)
        for i in range(len(queries)):
            q = queries[i]
            MP_form = '+'.join(q.split('+')[1:])
            r = synthetiser.lookup(q)
            try:
                item = r[0][0].split("@")[0], q_translations[i]
                results[MP_form].append(item[0])
            except:
                pass
        return results

    def __generator_queries__(self, lemma, pos):
        d = self.pos_dict[pos]
        queries = []
        query_trans = []

        for x in d["1st"]:
            for y in d["2nd"]:
                for z in d["3rd"]:
                    query = lemma + "+" + pos + x + y + z
                    queries.append(query)
                    query_trans.append(self.__get_trans__([x, y, z]))
            for c in d["comp"]:
                query = lemma + "+" + pos + x + c
                queries.append(query)
                query_trans.append(self.__get_trans__([x, c]))
        if pos == "N":
            more_queries = []
            more_trans = []
            nums = ["Sg", "Pl"]
            pers = ["1", "2", "3"]
            for i in range(len(queries)):
                query = queries[i]
                for num in nums:
                    for per in pers:
                        more_queries.append(query + "+Px" + num + per)
                        more_trans.append(query_trans[i] + self.__get_trans__(["Px", num, per]))
            queries.extend(more_queries)
            query_trans.extend(more_trans)

        if pos == "A":
            queries.append(lemma + "+A+Attr")
            query_trans.append("Attribuutti")

        return queries, query_trans

    def generate_uralicNLP(self, lang, lemma, pos, *args, **kwargs):
        if type(lang) is not str:
            lang = str(lang)

        generated_forms = defaultdict(list)
        if uralicApi.is_language_installed(lang):
            if pos in self.default_forms:
                poses = self.default_forms[pos]
                for f in poses:
                    results = uralicApi.generate(lemma + '+' + f, lang, **kwargs)
                    for r in results:
                        generated_forms[f].append(r[0].split('@')[0], )
        return generated_forms

    def generate(self, lang, lemma, pos):
        if type(lang) is not str:
            lang = str(lang)
        generated_forms = defaultdict(list)
        try:
            if lang == 'fin':
                generated_forms = self.generate_uralicNLP(lang, lemma, pos)
            else:
                if lang in self.get_supported_languages():
                    _method = getattr(self, '__inflect_%s__' % lang)
                    generated_forms = _method(lemma, pos)
                else:
                    generated_forms = self.generate_uralicNLP(lang, lemma, pos)
        except Exception as e:
            pass

        return generated_forms
