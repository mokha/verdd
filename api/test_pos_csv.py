"""The rules for reading an approved POS list. Plain unittest: no database or Django needed."""
import os
import tempfile
import unittest
from types import SimpleNamespace

from api.pos_csv import (
    ALREADY, CHANGED, MISMATCH, MISSING, WRONG_CSV_POS,
    converted_row, judge, read_approved, same_text, write_csv,
)

HEADER = "ID,Language,Lexeme,POS,Contlex,Inflex Type\n"


def entry(language="fin", lexeme="Pietari", pos="N"):
    return SimpleNamespace(language_id=language, lexeme=lexeme, pos=pos)


class ReadApprovedTests(unittest.TestCase):
    def test_header_is_kept_and_rows_are_read(self):
        parsed = read_approved(HEADER + "12,fin,Pietari,N,PROPER_NOUN,\n13,fin,Ruotsi,N,PROPER_NOUN,\n")
        self.assertEqual(parsed.header, [["ID", "Language", "Lexeme", "POS", "Contlex", "Inflex Type"]])
        self.assertEqual([(r.id, r.language, r.lexeme, r.pos) for r in parsed.rows],
                         [(12, "fin", "Pietari", "N"), (13, "fin", "Ruotsi", "N")])

    def test_header_in_another_language_and_no_header_at_all(self):
        parsed = read_approved("Tunnus,Kieli,Sana,Sanaluokka\n1,fin,Aatu,N\n")
        self.assertEqual(len(parsed.header), 1)
        self.assertEqual(len(parsed.rows), 1)
        self.assertEqual(read_approved("1,fin,Aatu,N\n").header, [])

    def test_semicolons_tabs_bom_and_blank_lines(self):
        for text in ("﻿ID;Language;Lexeme;POS\n\n1;fin;Aatu;N\n", "ID\tLanguage\tLexeme\tPOS\n1\tfin\tAatu\tN\n"):
            parsed = read_approved(text)
            self.assertEqual([(r.id, r.lexeme) for r in parsed.rows], [(1, "Aatu")], repr(text))

    def test_quoted_lexeme_with_a_comma_stays_whole(self):
        parsed = read_approved('1,fin,"Aatu, Pietari",N\n')
        self.assertEqual(parsed.rows[0].lexeme, "Aatu, Pietari")

    def test_bad_rows_are_set_aside_not_fatal(self):
        parsed = read_approved(HEADER + "1,fin,Aatu,N,x,\nabc,fin,Bad,N,x,\n2,fin,Short\n3,fin,Eero,N,x,\n")
        self.assertEqual([r.id for r in parsed.rows], [1, 3])
        self.assertEqual([(line, "not a number" in why, "found 3" in why) for line, _, why in parsed.unreadable],
                         [(3, True, False), (4, False, True)])

    def test_repeated_ids_are_counted_and_kept_once(self):
        parsed = read_approved("1,fin,Aatu,N\n1,fin,Aatu,N\n2,fin,Eero,N\n")
        self.assertEqual([r.id for r in parsed.rows], [1, 2])
        self.assertEqual(parsed.duplicates, 1)

    def test_nothing_numeric_means_no_rows(self):
        self.assertEqual(read_approved(HEADER).rows, [])


class JudgeTests(unittest.TestCase):
    def row(self, text="12,fin,Pietari,N,PROPER_NOUN,\n"):
        return read_approved(text).rows[0]

    def test_a_matching_row_may_be_converted(self):
        self.assertIsNone(judge(self.row(), entry(), "N", "Prop"))

    def test_each_way_a_row_is_refused(self):
        self.assertEqual(judge(self.row(), None, "N", "Prop"), MISSING)
        self.assertEqual(judge(self.row(), entry(language="sms"), "N", "Prop"), MISMATCH)
        self.assertEqual(judge(self.row(), entry(lexeme="Pietar"), "N", "Prop"), MISMATCH)
        self.assertEqual(judge(self.row("12,fin,Pietari,V,\n"), entry(), "N", "Prop"), WRONG_CSV_POS)
        self.assertEqual(judge(self.row(), entry(pos="Prop"), "N", "Prop"), ALREADY)
        self.assertEqual(judge(self.row(), entry(pos="V"), "N", "Prop"), CHANGED)

    def test_pos_is_compared_exactly(self):
        self.assertEqual(judge(self.row("12,fin,Pietari,n,\n"), entry(pos="n"), "N", "Prop"), WRONG_CSV_POS)
        self.assertEqual(judge(self.row(), entry(pos="n"), "N", "Prop"), CHANGED)

    def test_accents_match_however_they_are_composed(self):
        composed, decomposed = "Mañana", "Mañana"
        self.assertNotEqual(composed, decomposed)
        self.assertTrue(same_text("Äiti", "Äiti"))
        row = self.row("1,fin,%s,N\n" % decomposed)
        self.assertIsNone(judge(row, entry(lexeme=composed), "N", "Prop"))


class WriteTests(unittest.TestCase):
    def test_only_the_pos_cell_changes(self):
        row = read_approved(HEADER + '12,fin,"Aatu, I",N,PROPER_NOUN,3\n').rows[0]
        self.assertEqual(converted_row(row, "Prop"), ["12", "fin", "Aatu, I", "Prop", "PROPER_NOUN", "3"])
        self.assertEqual(row.raw[3], "N", "the row read is not altered")

    def test_written_file_reads_back(self):
        parsed = read_approved(HEADER + '12,fin,"Aatu, I",N,PROPER_NOUN,3\n')
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "out.csv")
            write_csv(path, parsed.header + [converted_row(r, "Prop") for r in parsed.rows])
            with open(path, encoding="utf-8-sig") as handle:
                again = read_approved(handle.read())
        self.assertEqual(again.header, parsed.header)
        self.assertEqual([(r.id, r.lexeme, r.pos) for r in again.rows], [(12, "Aatu, I", "Prop")])


if __name__ == "__main__":
    unittest.main()
