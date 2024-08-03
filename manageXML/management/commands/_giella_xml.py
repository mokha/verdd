import io
import re
from collections import defaultdict, OrderedDict


class GiellaXML:
    def __init__(self, *args, **kwargs):
        self.lang = kwargs.get("lang")
        self.elements = kwargs.get("elements", [])

    class Item(OrderedDict):
        def __init__(self, *args, **kwargs):
            super(GiellaXML.Item, self).__init__(*args, **kwargs)
            self.text = kwargs.get("text", "").strip()
            _dic = kwargs.get("attributes", None)
            self.attributes = (
                _dic
                if _dic is not None and isinstance(_dic, dict)
                else defaultdict(str)
            )

        def filtered_attributes(self, ignore=("pos", "lang", "hid", "contlex")):
            return {k: v for k, v in self.attributes.items() if k not in ignore}

        def __repr__(self):
            return self.text

        def __getattr__(self, item):
            item = item.lower()
            if item == "homoid":
                return (
                    int(re.sub(r"hom", "", self.attributes.get("hid", "1"), flags=re.I))
                    - 1
                )
            return self.attributes.get(item, "")

    @staticmethod
    def odict2item(value):
        if isinstance(value, OrderedDict):
            d = GiellaXML.Item()
            for k, v in value.items():
                if isinstance(v, OrderedDict):  # assumes v is also list of pairs
                    d[k.lower()] = d[k] = [GiellaXML.odict2item(v)]
                elif isinstance(v, list):
                    d[k.lower()] = d[k] = [GiellaXML.odict2item(_v) for _v in v]
                elif isinstance(v, str):
                    if k.startswith("@"):
                        d.attributes[k[1:]] = v
                    elif k.startswith("#"):
                        d.text = v
            return d
        elif isinstance(value, str):
            d = GiellaXML.Item()
            d.text = value
            return d
        return value

    @staticmethod
    def parse_file(filename):
        with io.open(filename, "r", encoding="utf-8") as fp:
            import xmltodict

            namespaces = {
                "http://www.w3.org/XML/1998/namespace": "xml",
            }
            x = xmltodict.parse(
                fp.read(), process_namespaces=True, namespaces=namespaces
            )
            r = GiellaXML.odict2item(x["r"])
            lang = r.attributes.get("xml:lang")
            g_xml = GiellaXML(lang=lang)
            g_xml.elements = r["e"] if "e" in r else []
            return g_xml
