"""Reading an approved list of lexemes for a POS conversion.

The list is the CSV that Ve'rdd's lexeme search exports (ID, Language, Lexeme, POS, Contlex, Inflex Type,
...), after a person has deleted the rows they do not approve. Nothing here touches the database, so the
rules can be tested without one; api/management/commands/convert_pos_csv.py applies them.
"""
import csv
import io
import unicodedata
from dataclasses import dataclass, field

DELIMITERS = ",;\t"  # a spreadsheet may save with a semicolon or a tab
POS_COLUMN = 3  # ID, Language, Lexeme, POS

# why a row is not converted
INVALID = "invalid"
MISSING = "missing"
MISMATCH = "mismatch"
WRONG_CSV_POS = "csv-pos"
ALREADY = "already"
CHANGED = "changed"
CLASH = "clash"

REASONS = {
    INVALID: "the row cannot be read",
    MISSING: "no entry with this ID in Ve'rdd",
    MISMATCH: "the ID belongs to another language or headword than the row says (old list, or a wrong ID)",
    WRONG_CSV_POS: "the row's POS is not the one to convert from",
    ALREADY: "already has the target POS",
    CHANGED: "its POS in Ve'rdd is no longer the one to convert from",
    CLASH: "another entry with the same headword, language and homonym number already has the target POS: merge the two",
}


@dataclass
class ApprovedRow:
    line: int  # line in the file, for messages
    raw: list  # every cell as it was in the file
    id: int
    language: str
    lexeme: str
    pos: str


@dataclass
class ApprovedList:
    header: list = field(default_factory=list)  # leading rows that start with no ID (the header, in any language)
    rows: list = field(default_factory=list)
    unreadable: list = field(default_factory=list)  # (line, raw cells, reason)
    duplicates: int = 0  # rows repeating an ID that was already listed


def same_text(a, b):
    """Equal as text, whatever way an editor composed the accents."""
    return unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b)


def _delimiter(text):
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=DELIMITERS).delimiter
    except csv.Error:
        return ","


def read_approved(text):
    """Parse the CSV text. Rows before the first ID are the header; a later row without a numeric
    ID, or with fewer than four cells, is set aside as unreadable instead of stopping the run."""
    text = text.lstrip("﻿")  # the byte-order mark Excel adds
    parsed = ApprovedList()
    seen = set()
    started = False
    for line, cells in enumerate(csv.reader(io.StringIO(text), delimiter=_delimiter(text)), start=1):
        if not any(cell.strip() for cell in cells):
            continue
        first = cells[0].strip()
        if not started and not first.isdigit():
            parsed.header.append(cells)
            continue
        started = True
        if not first.isdigit():
            parsed.unreadable.append((line, cells, "the ID %r is not a number" % first))
        elif len(cells) <= POS_COLUMN:
            parsed.unreadable.append((line, cells, "expected ID, language, lexeme and POS: found %d cell(s)" % len(cells)))
        elif int(first) in seen:
            parsed.duplicates += 1
        else:
            seen.add(int(first))
            parsed.rows.append(ApprovedRow(
                line=line, raw=cells, id=int(first),
                language=cells[1].strip(), lexeme=cells[2], pos=cells[POS_COLUMN].strip(),
            ))
    return parsed


def judge(row, entry, from_pos, to_pos):
    """None when the row may be converted, else the reason (a key of REASONS).

    `entry` is the lexeme as Ve'rdd has it now (anything with language_id, lexeme and pos), or None.
    POS values are compared exactly: 'prop' is not 'Prop'."""
    if entry is None:
        return MISSING
    if entry.language_id != row.language or not same_text(entry.lexeme, row.lexeme):
        return MISMATCH
    if row.pos != from_pos:
        return WRONG_CSV_POS
    if entry.pos == to_pos:
        return ALREADY
    if entry.pos != from_pos:
        return CHANGED
    return None


def converted_row(row, to_pos):
    """The row as it was in the file, with only the POS cell replaced."""
    cells = list(row.raw)
    cells[POS_COLUMN] = to_pos
    return cells


def write_csv(path, rows):
    # utf-8-sig so a spreadsheet opens the accents correctly
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)
