import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from manageXML.models import *
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DataImporter:
    """
    A class responsible for importing data from JSON and XML files into Django models.
    """

    def __init__(self, json_file, xml_file, user):
        self.user = user
        self.pk_mapping = defaultdict(dict)
        self.model_map = {
            "datafile": DataFile,
            "lexeme": Lexeme,
            "relation": Relation,
            "relationexample": RelationExample,
            "source": Source,
            "miniparadigm": MiniParadigm,
            "affiliation": Affiliation,
            "relationmetadata": RelationMetadata,
            "relationexamplerelation": RelationExampleRelation,
        }

        self.json_data = self.load_json(json_file)
        self.data = defaultdict(dict)

        # Process JSON data
        for item in self.json_data:
            model_name = item["model"].split(".")[-1].lower()
            if model_name in self.model_map:
                pk = item["pk"]
                self.data[model_name][pk] = item["fields"]

        self.xml_mapping = self.process_xml_file(xml_file)

    def process_xml_file(self, xml_file):
        """Process XML file to extract specific data fields for later use."""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        xml_mapping = defaultdict(list)

        for e in root.findall("e"):
            lg = e.find("lg")
            if lg is not None:
                l = lg.find("l")
                if l is not None:
                    lexeme = l.text
                    pos = l.get("pos")
                    hid = int(l.get("hid", "Hom1").replace("Hom", "")) - 1
                    stg = lg.find("stg")
                    if stg is not None:
                        st = stg.find("st")
                        if st is not None:
                            contlex = st.get("contlex")
                            varId = int(st.get("varid", "1")) - 1
                            text = st.text

                            xml_mapping[(lexeme, pos, hid)].append(
                                {"contlex": contlex, "text": text, "varId": varId}
                            )
        return xml_mapping

    def load_json(self, file_path):
        """Load JSON file and return the data."""
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def delete_all_lexemes(self, language):
        """Delete all lexemes of a given language."""
        Lexeme.objects.filter(language=language).delete()
        logger.info(f"Deleted all Lexemes for Language: {language}")

    def import_data(self):
        """Main method to coordinate the importing of all data."""
        self.create_datafiles()
        self.create_lexemes()
        self.create_affiliations()
        self.create_relations()
        self.create_relation_examples()
        self.create_sources()
        self.create_mini_paradigms()
        self.create_relation_metadata()
        self.create_relation_example_relations()

    def create_datafiles(self):
        """Create or update DataFile entries from provided data."""

        created_count = 0
        for pk, fields in self.data["datafile"].items():
            datafile, created = DataFile.objects.update_or_create(
                name=fields["name"],
                lang_source_id=fields["lang_source"],
                lang_target_id=fields["lang_target"],
            )

            created_count += 1 if created else 0

            self.pk_mapping["datafile"][pk] = datafile.id

        logger.info(f"Created {created_count} DataFiles")

    def create_lexemes(self):
        """Create or update Lexeme entries and their related Stems from XML data."""

        created_count = 0
        for pk, fields in self.data["lexeme"].items():
            lexeme, created = Lexeme.objects.get_or_create(
                lexeme=fields["lexeme"],
                pos=fields["pos"],
                homoId=fields["homoId"],
                language_id=fields["language"],
                defaults={
                    "imported_from_id": self.pk_mapping["datafile"].get(
                        fields["imported_from"]
                    ),
                    "contlex": fields["contlex"],
                    "notes": fields["notes"],
                    "checked": fields["checked"],
                    "specification": fields["specification"],
                    "changed_by": self.user,
                },
            )
            created_count += 1 if created else 0
            self.pk_mapping["lexeme"][pk] = lexeme.id

            if (lexeme.lexeme, lexeme.pos, lexeme.homoId) in self.xml_mapping:
                stem_data = self.xml_mapping[(lexeme.lexeme, lexeme.pos, lexeme.homoId)]
                for _stem in stem_data:
                    Stem.objects.get_or_create(
                        lexeme=lexeme,
                        text=_stem["text"],
                        contlex=_stem["contlex"],
                        defaults={
                            "order": _stem["varId"],
                        },
                    )

        logger.info(f"Created {created_count} Lexemes")

    def create_relations(self):
        """Create or update Relation entries from provided data."""

        for pk, fields in self.data["relation"].items():
            relation, created = Relation.objects.update_or_create(
                lexeme_from_id=self.pk_mapping["lexeme"].get(fields["lexeme_from"]),
                lexeme_to_id=self.pk_mapping["lexeme"].get(fields["lexeme_to"]),
                type=fields["type"],
                defaults={
                    "notes": fields["notes"],
                    "checked": fields["checked"],
                    "changed_by": self.user,
                },
            )
            self.pk_mapping["relation"][pk] = relation.id
            logger.info(
                f"{'Created' if created else 'Updated'} Relation: {relation.id}"
            )

    def create_relation_examples(self):
        """Create or update RelationExample entries from provided data."""
        for pk, fields in self.data["relationexample"].items():
            relation_example, created = RelationExample.objects.update_or_create(
                relation_id=self.pk_mapping["relation"].get(fields["relation"]),
                language_id=fields["language"],
                text=fields["text"],
                defaults={
                    "source": fields["source"],
                    "notes": fields["notes"],
                    "changed_by": self.user,
                },
            )
            self.pk_mapping["relationexample"][pk] = relation_example.id
            logger.info(
                f"{'Created' if created else 'Updated'} Relation Example: {relation_example.id}"
            )

    def create_sources(self):
        """Create or update Source entries from provided data."""
        for pk, fields in self.data["source"].items():
            source, created = Source.objects.update_or_create(
                relation_id=self.pk_mapping["relation"].get(fields["relation"]),
                name=fields["name"],
                defaults={
                    "page": fields["page"],
                    "type": fields["type"],
                    "notes": fields["notes"],
                    "changed_by": self.user,
                },
            )
            self.pk_mapping["source"][pk] = source.id
            logger.info(f"{'Created' if created else 'Updated'} Source: {source.id}")

    def create_mini_paradigms(self):
        """Create or update MiniParadigm entries from provided data."""
        for pk, fields in self.data["miniparadigm"].items():
            mini_paradigm, created = MiniParadigm.objects.update_or_create(
                lexeme_id=self.pk_mapping["lexeme"].get(fields["lexeme"]),
                msd=fields["msd"],
                wordform=fields["wordform"],
                defaults={
                    "changed_by": self.user,
                },
            )
            self.pk_mapping["miniparadigm"][pk] = mini_paradigm.id
            logger.info(
                f"{'Created' if created else 'Updated'} Mini Paradigm: {mini_paradigm.id}"
            )

    def create_affiliations(self):
        """Create or update Affiliation entries from provided data."""
        for pk, fields in self.data["affiliation"].items():
            affiliation, created = Affiliation.objects.update_or_create(
                lexeme_id=self.pk_mapping["lexeme"].get(fields["lexeme"]),
                title=fields["title"],
                link=fields["link"],
                type=fields["type"],
                defaults={
                    "checked": fields["checked"],
                    "changed_by": self.user,
                },
            )
            self.pk_mapping["affiliation"][pk] = affiliation.id
            logger.info(
                f"{'Created' if created else 'Updated'} Affiliation: {affiliation.id}"
            )

    def create_relation_metadata(self):
        """Create or update RelationMetadata entries from provided data."""
        for pk, fields in self.data["relationmetadata"].items():
            relation_metadata, created = RelationMetadata.objects.update_or_create(
                relation_id=self.pk_mapping["relation"].get(fields["relation"]),
                language_id=fields["language"],
                text=fields["text"],
                type=fields["type"],
                defaults={
                    "changed_by": self.user,
                },
            )
            self.pk_mapping["relationmetadata"][pk] = relation_metadata.id
            logger.info(
                f"{'Created' if created else 'Updated'} Relation Metadata: {relation_metadata.id}"
            )

    def create_relation_example_relations(self):
        """Create or update RelationExampleRelation entries from provided data."""
        for pk, fields in self.data["relationexamplerelation"].items():
            relation_example_relation, created = (
                RelationExampleRelation.objects.update_or_create(
                    example_from_id=self.pk_mapping["relationexample"].get(
                        fields["example_from"]
                    ),
                    example_to_id=self.pk_mapping["relationexample"].get(
                        fields["example_to"]
                    ),
                    defaults={
                        "notes": fields["notes"],
                    },
                )
            )
            self.pk_mapping["relationexamplerelation"][
                pk
            ] = relation_example_relation.id
            logger.info(
                f"{'Created' if created else 'Updated'} Relation Example Relation: {relation_example_relation.id}"
            )


class Command(BaseCommand):
    """
    Django management command to import data from JSON and XML into the database.
    """

    help = "Imports JSON and XML data into the database, ensuring all relationships and dependencies are respected."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json_file", type=str, help="Path to the JSON file containing the data."
        )
        parser.add_argument(
            "--xml_file", type=str, help="Path to the XML file containing the data."
        )
        parser.add_argument(
            "-u",
            "--user_id",
            type=int,
            help="ID of the User who is importing the data.",
        )

    def handle(self, *args, **options):
        # try:
        user = (
            User.objects.get(pk=options["user_id"]) if options.get("user_id") else None
        )
        importer = DataImporter(
            json_file=options["json_file"], xml_file=options["xml_file"], user=user
        )
        importer.delete_all_lexemes("sms")
        importer.import_data()
        self.stdout.write(self.style.SUCCESS("Successfully imported all data."))

        # except User.DoesNotExist:
        #     raise CommandError("User with provided ID does not exist.")
        # except FileNotFoundError as e:
        #     raise CommandError(f"File not found: {str(e)}")
        # except Exception as e:
        #     logger.error(f"Error during import: {str(e)}")
        #     raise CommandError(f"An error occurred: {str(e)}")
