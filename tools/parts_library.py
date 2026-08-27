"""Turn a submitted list of LEGO design numbers into a .parts library Sangala Blocks can import.

The format is the one specified in Documents\\Adding LEGO Blocks: a plain text file goes in, one part
to a line - the design number, then a quantity and a color if they are known - and a .parts file
comes out, JSON in the same shape as the .block file the application already writes.

    python tools/parts_library.py "Projects/Starter Set.txt"
    python tools/parts_library.py "Projects/Starter Set.txt" -o "Projects/Starter Set.parts"

EVERY FIELD BUT COLOR AND QUANTITY IS DERIVED FROM LDRAW, never from the submitted line. The number
is resolved through any redirection (3040 answers "~Moved to 3040b"), the name is the part file's
own first line, the footprint and height are measured, and the color is matched against
LDConfig.ldr. A line that cannot be resolved is REPORTED AND LEFT OUT, so a mistyped number shows up
as a line to correct rather than as a part that does not exist.

THREE MEASUREMENTS NEED CARE. A measured height includes the stud - a brick is 28 LDU, being 24 of
body and 4 of stud - and the application's own size table records the BODY, so the stud is subtracted
from anything that has one. A measured footprint is the whole bounding box, which for a slope is
neither the way it lies nor what it rests on - see `footprint`, which is the correction. And a part
is stored under the number that was SUBMITTED, because that is the number a builder orders by; the
redirection matters only for reading the geometry.

Where the specification and this script differ, and the difference is deliberate: the document says
shape is classified from the geometry. It is classified here from the part's own description, which
is the library's own authority on what a part is and is far steadier than inferring roundness from
triangles. The measurements still come from the geometry.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldparts

ROOT = ldparts.ROOT
PLATE_LDU = 8.0
STUD_LDU = 4.0


def colors():
    """name (lowercased) -> (canonical name, code), from the library's own palette file."""
    out = {}
    path = os.path.join(ROOT, "LDConfig.ldr")
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"0 !COLOUR\s+(\S+)\s+CODE\s+(\d+)", line.strip())
        if m:
            name = m.group(1).replace("_", " ")
            out[name.lower()] = (name, int(m.group(2)))
            # LDRAW SPELLS IT GREY; THIS PROJECT WRITES GRAY, and so does the application's own
            # palette. Both spellings are registered so that a submitted list in either is matched
            # rather than reported as an unknown color.
            if "grey" in name.lower():
                out[name.lower().replace("grey", "gray")] = (name, int(m.group(2)))
            elif "gray" in name.lower():
                out[name.lower().replace("gray", "grey")] = (name, int(m.group(2)))
    return out


def has_stud(path, seen=None):
    """Does anything in this part reference a stud primitive? Decides whether to subtract one."""
    seen = seen if seen is not None else set()
    key = os.path.basename(path).lower()
    if key in seen:
        return False
    seen.add(key)
    for line in open(path, encoding="utf-8", errors="replace"):
        t = line.strip()
        if not t.startswith("1 "):
            continue
        bits = t.split()
        if len(bits) < 15:
            continue
        ref = bits[14].replace("\\", "/").split("/")[-1].lower()
        if ref.startswith("stud"):
            return True
        sub = ldparts.locate(ref)
        if sub and has_stud(sub, seen):
            return True
    return False


IDENT = ([[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]], [0.0, 0.0, 0.0])


def compose(outer, inner):
    """Put a sub-file's own placement into its parent's frame: outer applied to inner."""
    (a, t), (b, u) = outer, inner
    m = [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    p = [a[i][0] * u[0] + a[i][1] * u[1] + a[i][2] * u[2] + t[i] for i in range(3)]
    return (m, p)


def side_studs(path, w, xf=IDENT, depth=0, seen=(), out=None):
    """Where a part carries studs on a FACE rather than on top, in the plan view's own units.

    A side-stud brick's studs are the whole reason it is in a design - the wings hang on them - and
    the standing view is a profile, so those studs point straight at the viewer and belong on the
    drawing. Nothing in a .parts entry said they existed, so 2434 arrived as a plain block and Glen
    had to open the 3D view to see what it was for (2026-08-17: "I see the studs on the side in the
    3D view but not in the 2d view").

    MEASURED, NOT READ OFF THE NAME. "with Studs on Sides" says nothing about how many or where, and
    the four side-stud parts in the crane's library carry 8, 4, 2 and 1 of them. An LDraw stud primitive
    is a cylinder along its own +Y, so a type-1 reference maps that axis to the matrix's middle
    column; where the image of +Y is horizontal rather than vertical, the stud is on a face. The
    matrix may also SCALE (stud4 arrives 11x tall), so it is the dominant direction that decides,
    never the length.

    Returned as [across, down] per stud: `across` in studs from the part's left edge, `down` in
    plates from the top of its body - the two units the plan view already draws in. The LDraw origin
    sits at the top of the body and centred across it, which is the same convention the height
    measurement above depends on. Both faces are read and the positions DEDUPED: seen in profile the
    near and far studs land on the same spot, and the drawing shows a stud, not a count.
    """
    out = [] if out is None else out
    key = os.path.normcase(path)
    if depth > 12 or key in seen:
        return out
    seen = seen + (key,)
    for line in open(path, encoding="utf-8", errors="replace"):
        t = line.split()
        if not t or t[0] != "1" or len(t) < 15:
            continue
        try:
            v = [float(x) for x in t[2:14]]
        except ValueError:
            continue
        here = compose(xf, ([[v[3], v[4], v[5]], [v[6], v[7], v[8]], [v[9], v[10], v[11]]],
                            [v[0], v[1], v[2]]))
        ref = " ".join(t[14:]).replace("\\", "/").split("/")[-1].lower()
        if ref.startswith("stud"):
            ax, ay, az = here[0][0][1], here[0][1][1], here[0][2][1]     # image of the stud's +Y
            if abs(ay) >= max(abs(ax), abs(az)):
                continue                                                 # up or down: an ordinary stud
            across = (here[1][0] + w * ldparts.STUD / 2) / ldparts.STUD
            down = here[1][1] / PLATE_LDU
            pos = [round(across, 3), round(down, 3)]
            if pos not in out:
                out.append(pos)
            continue
        sub = ldparts.locate(ref)
        if sub:
            side_studs(sub, w, here, depth + 1, seen, out)
    return out


def top_studs(path, box, w, d):
    """Where a part's studs actually sit on its top, WHEN THEY DO NOT FILL IT.

    Glen, 2026-08-17, looking at a 4 x 4 wedge on the plan: the drawing put a stud in every cell of
    the footprint, so a part with two studs came out with sixteen and the ones past the taper sat
    outside its own outline. 6069 has exactly TWO, side by side at the wide end - which is what the
    LDraw file says and what Jo's photograph of the part shows.

    Measured the same way the side studs are: an upward stud is a reference to a stud primitive whose
    axis is vertical. The tubes UNDERNEATH are stud primitives too (stud3, stud4), so the test is the
    top face - a stud on top sits at the part's own origin plane, which LDraw puts at the top of the
    body, while the tubes hang below it.

    Returned as [across, down] per stud in STUDS, from the part's left edge and from the end that the
    plan view draws first. Measured off the box rather than assumed centred: a wedge's origin is not
    in the middle of its length (6069 runs -70 to +10 in z), so centring would place every stud on
    the wrong row.

    Omitted entirely when the studs DO fill the footprint, which is the ordinary case - an ordinary
    brick says nothing here and is drawn exactly as it always was.
    """
    minx, maxx, miny, maxy, minz, maxz = box
    out = []
    for name, pos, axis in _walk_studs(path):
        ax, ay, az = axis
        if abs(ay) < max(abs(ax), abs(az)):
            continue                                   # on a face: that is side_studs' business
        # A TUBE IS NOT A STUD, AND THE GEOMETRIC TEST ALONE CANNOT SAY SO. stud3 is "Stud Tube
        # Solid" and stud4 "Stud Tube Open" - the sockets underneath, which the position test was
        # meant to reject by asking whether they sit near the part's top face. That works while a
        # part's origin is at the top of its body, which is the usual arrangement. 93273's body lies
        # ENTIRELY above its origin, so its underside tube measured as near the top and was recorded
        # as a stud on a part that LEGO catalogs as "Double Curved Top (No Studs)" - which is what
        # Watts said before anyone measured anything (2026-08-27: "the block still has studs on top.
        # It should not"). Named outright, since the two files say what they are.
        if name.startswith("stud3") or name.startswith("stud4"):
            continue
        if pos[1] > miny + STUD_LDU + 0.5:
            continue                                   # a tube below the top face, not a stud on it
        across = (pos[0] - minx) / ldparts.STUD
        down = (maxz - pos[2]) / ldparts.STUD
        p = [round(across, 3), round(down, 3)]
        if p not in out:
            out.append(p)
    # THREE ANSWERS, NOT TWO. An empty list meant both "the studs fill the footprint, say nothing"
    # and "there are no studs at all", and those want opposite things on the page: the first should
    # draw a stud on every cell, the second none. None is returned as None so the caller can tell.
    if not out:
        return None
    return out if len(out) < w * d else []


def _walk_studs(path, xf=IDENT, depth=0, seen=(), out=None):
    """Every stud primitive in a part, with where it sits and which way its axis points."""
    out = [] if out is None else out
    key = os.path.normcase(path)
    if depth > 12 or key in seen:
        return out
    seen = seen + (key,)
    for line in open(path, encoding="utf-8", errors="replace"):
        t = line.split()
        if not t or t[0] != "1" or len(t) < 15:
            continue
        try:
            v = [float(x) for x in t[2:14]]
        except ValueError:
            continue
        here = compose(xf, ([[v[3], v[4], v[5]], [v[6], v[7], v[8]], [v[9], v[10], v[11]]],
                            [v[0], v[1], v[2]]))
        ref = " ".join(t[14:]).replace("\\", "/").split("/")[-1].lower()
        if ref.startswith("stud"):
            out.append((ref, here[1], (here[0][0][1], here[0][1][1], here[0][2][1])))
            continue
        sub = ldparts.locate(ref)
        if sub:
            _walk_studs(sub, here, depth + 1, seen, out)
    return out


def american(name):
    """LDraw writes British; every Sangala surface writes American (Glen, 2026-08-17, reading
    "Plate 1 x 2 with Groove with 1 Centre Stud" in the Library panel).

    The colors have been converted since this script was written - LDraw's file says Grey and the
    application's palette says Gray - and a part's NAME arrives by the same route and deserves the
    same treatment. Only whole words are replaced, and the capitalization of each is kept, so
    "Centre" becomes "Center" and a design number is never touched.
    """
    for brit, amer in (("Centre", "Center"), ("Centres", "Centers"), ("Grey", "Gray"),
                       ("Colour", "Color"), ("Colours", "Colors"), ("Moulded", "Molded")):
        name = re.sub(r"\b%s\b" % brit, amer, name)
        name = re.sub(r"\b%s\b" % brit.lower(), amer.lower(), name)
    return name


def classify(name):
    """kind and shape, from the part's own description.

    THE SHAPE MUST BE SPOKEN IN THE PAGE'S OWN VOCABULARY, which is rect, slope, invslope, round,
    cone and wedge - the names its drawing and its 3D build switch on. This wrote box/wedge/round
    instead, three words borrowed from the specification document, and the page has no idea what they
    mean: a cone arrived as "round" and was built as a cylinder with a stud on top (Glen, 2026-08-15,
    looking at one: "I don't know what that is, but it is not a cone"), and a slope would have arrived
    as a wedge plate. A vocabulary that only one side understands is not a vocabulary.
    """
    n = name.lower()
    if "inverted" in n and "slope" in n:
        return "invslope", "invslope"
    if "slope" in n:
        return "slope", "slope"
    if "cone" in n:
        return "cone", "cone"
    if "round" in n:
        return "round", "round"
    if n.startswith("tile"):
        return "tile", "rect"
    if "wedge" in n or "wing" in n:
        return "wedge", "wedge"
    if n.startswith("plate"):
        return "plate", "rect"
    if n.startswith("brick"):
        return "brick", "rect"
    return "other", "rect"


def resting(path, box):
    """What the part actually stands on, in studs, measured on its own underside.

    LDraw's +Y POINTS DOWN, so a part's underside is its MAXIMUM y, and the geometry sitting on that
    plane is the face it rests on. Returned as (x, z) in studs, or None where nothing lies flat.

    THIS REPLACES A RULE THAT WAS ONLY EVER RIGHT AT 45 DEGREES. "An inverted slope rests on one
    column less than its body" was measured on 3665 and 3660, which are 45s, and it is right for
    them - a 45 ramp spans two studs and hangs over one. A 33-degree ramp spans THREE and hangs over
    TWO: 4287a is 1 x 3 and rests on 1 x 1, 3747a is 2 x 3 and rests on 2 x 1, and subtracting one
    column put both of them a stud too deep. That is the same fault that once sat the crane's crest a
    stud into the plate, and CLAUDE.md already says why it keeps recurring: "no rule of the form 'a
    slope occupies N columns' can ever be right".

    So the underside is read off the part rather than derived from its angle, and the angle never has
    to be known. Every inverted slope in the catalog turns out to rest on exactly one stud along its
    ramp, whatever its pitch - but that is now an observation about the parts, not an assumption the
    script depends on.
    """
    pts = []
    ldparts._walk(path, ldparts.IDENT, 0, (), lambda x, y, z: pts.append((x, y, z)))
    floor = [q for q in pts if abs(q[1] - box[3]) < 0.6]
    if not floor:
        return None
    xs = [q[0] for q in floor]
    zs = [q[2] for q in floor]
    return ((max(xs) - min(xs)) / ldparts.STUD, (max(zs) - min(zs)) / ldparts.STUD)


def footprint(shape, w, dd, rest=None):
    """The measured bounding box -> what the part RESTS ON, which is what a .parts file states.

    A BOUNDING BOX CANNOT TELL YOU WHAT A PART STANDS ON, and writing it as though it could is what
    put the crest a stud too deep: dragging a part out of the Library panel builds it straight from
    the w and d written here, so an inverted slope arrived two studs deep, hung off the back edge of
    the plate it was standing on, and looked perfect from the front because the error ran straight
    away from the camera. The Part menu was right all along - it reads the application's own size
    table, which states these footprints outright. This makes the file say the same thing.

    Two corrections, and both are measured facts about 45-degree slopes rather than conventions:
      - THE RAMP RUNS ALONG THE PART'S OWN Z, on every one of them (3040, 3039, 3037, 3665, 3660).
        The standing view is the figure in profile and needs that ramp ACROSS the screen, so the
        ramped side takes the COLUMNS and the other side becomes the rows. That is a straight swap.
      - AN INVERTED SLOPE RESTS ON LESS THAN IT COVERS. Its underside is cut away, so it attaches to
        one stud along the ramp and the rest of the body hangs over the next; the footprint is one
        column short of the body, and the application adds that column back as the overhang. An
        ordinary slope rests on all of itself and is not shortened - the two are opposites, which is
        why no single rule about "how many columns a slope takes" can ever be right.

    Checked against the application's own table, which was measured independently: 3040 -> 2 x 1,
    3039 -> 2 x 2, 3037 -> 2 x 4, 3665 -> 1 x 1, 3660 -> 1 x 2. All five agree.
    """
    if rest:
        # THE FOOTPRINT IS THE RESTING FACE, IN BOTH DIRECTIONS. It was the measured box, corrected
        # for inverted slopes along one axis only, and that was enough until a part hung over its
        # base BOTH ways: 3676 covers 2 x 2 and rests on 1 x 1, 13349 covers 4 x 4 and rests on
        # 2 x 1. Neither is describable by shortening a single side.
        # An ordinary brick's underside is hollow but its walls reach the full outline, so this
        # returns the box for it and nothing changes - checked across all 73 parts of the kit, where
        # 71 came out identical and the two that moved are the two measured wrong.
        w, dd = int(round(rest[0])), int(round(rest[1]))
    if shape in ("slope", "invslope", "bow"):
        w, dd = dd, w                  # the ramp runs along z, and the profile needs it across
    elif not rest and shape == "invslope":
        w = max(1, w - 1)
    return max(1, w), max(1, dd)


# A SECTION HEADING IN THE LIST, naming the bin every part below it belongs to until the next one:
#
#     :kind knobbed "Knobbed Brick" rect
#
# the kind, then the label to show on its menu button, then an optional shape. Anything omitted is
# left to classify() below, which is what an undeclared list (Crane.txt, Starter Set.txt) still uses.
#
# WHY THE LIST SAYS THIS RATHER THAN THE SCRIPT INFERRING IT. classify() reads the part's LDraw
# description, which is the library's own authority on what a part is and is right for the categories
# it was written for. It cannot be right for a category nobody has read the descriptions of: LDraw
# calls 87087 "Brick 1 x 1 with Stud on 1 Side", and a rule matching "Knob" - the word the collector
# uses - would file none of the thirteen knobbed bricks correctly. Rather than write patterns against
# text nobody has checked, the person who assembled the list states the bin. They know; the library
# measures. That also makes the file its own answer to how the parts are labeled and sorted, since
# the order of the sections is the order of the rows in the Library panel.
DIRECTIVE = re.compile(r'^:kind\s+(\S+)(?:\s+"([^"]*)")?(?:\s+(\S+))?\s*$')


def suggest(note, limit=4):
    """Candidates for a number that would not resolve, from the collector's own description.

    THE SPECIFICATION ASKED FOR THIS AND IT WAS NEVER BUILT. Documents\Adding LEGO Blocks: "Where a
    part is known by sight rather than by number, its description may be written instead ... and the
    builder reports what it matched so the match can be confirmed before the library is written."

    Until now an unresolvable line was a dead end that a person had to close by searching the catalog
    by hand and editing the number in (Watts, 2026-08-27: "Why do I need to manually change numbers?
    Is this something you cannot do?"). The catalog is right here and the line already carries a
    description in its comment, so the search is the script's work, not the reader's.

    IT SUGGESTS AND DOES NOT SUBSTITUTE. A part is measured, never remembered - that rule is the
    reason this tool exists - and a plausible name is not a measurement. So the candidates are
    printed for a person to confirm, which is what the specification asked for.

    The description is matched loosely: its digits and its words must all appear, in any order, so
    "Slope 2 x 3, Inv." finds a part LDraw writes "Slope Brick 45  2 x  3 Inverted" whichever way
    round the size is written. Punctuation and the abbreviations a collector writes are dropped.
    """
    if not note:
        return []
    ABBREV = {"inv": "inverted", "rnd": "round", "sq": "square"}
    words = [ABBREV.get(w, w) for w in re.split(r"[^a-z0-9]+", note.lower()) if w]
    words = [w for w in words if w != "x"]
    if not words:
        return []
    noun = words[0]
    # A REPEATED DIGIT MUST BE MATCHED TWICE. Checking each word for mere presence let "Slope 2 x 2"
    # match a part written "2 x 1", because the second 2 asked the same question as the first and got
    # the same yes - and the wrong part then led the list, which is the one place a suggestion must
    # not be careless. Digits are counted against the description's own words; the rest stay a
    # substring test, so "inverted" still finds "Inverted without Inner Stopper Ring".
    from collections import Counter
    want_digits = Counter(w for w in words if w.isdigit())
    want_words = [w for w in words if not w.isdigit()]
    out = []
    for num, desc in ldparts.catalog(quiet=True):
        low = desc.lower()
        if low.startswith("~moved to") or low.startswith("~renamed"):
            continue
        hay = " ".join(low.split())
        have = Counter(t for t in re.split(r"[^a-z0-9]+", hay) if t.isdigit())
        if all(have[d] >= n for d, n in want_digits.items()) and all(w in hay for w in want_words):
            out.append((num, " ".join(desc.split()), hay))
            if len(out) > 400:
                break                      # a description this loose is not worth ranking
    # RANKED, BECAUSE A LIST ORDERED BY PART NUMBER IS NOT A SUGGESTION. "Brick 2 x 4" matched three
    # slopes before this, on nothing more than the 2 and the 4, and the right answer led only by the
    # luck of its number. What a collector writes first is the NOUN - Slope, Brick, Plate - and LDraw
    # writes the same word first, so a description that opens with it is the better candidate; among
    # those, the shortest is the plainest part rather than a variant with extras.
    out.sort(key=lambda r: (not r[2].startswith(noun), len(r[2]), r[0]))
    return [(num, desc) for num, desc, _ in out[:limit]]


def read_list(path):
    """One part to a line: number[ -> ldraw][, qty][, color], under an optional :kind heading.

    THE NUMBER MAY NAME TWO PARTS, and this is not pedantry - it is the only way two of the bricks
    in the Sangala kit can be ordered AND measured. A design number is what a builder orders by, and
    LDraw usually files a part under that same number, redirecting from it where the mould has a
    variant (3040 answers "~Moved to 3040b"). But LEGO has renumbered parts that LDraw still files
    under the old number with no redirect between them: Brick 2 x 6 is design 44237 and LDraw 2456,
    Brick 2 x 8 is design 93888 and LDraw 3007. Given one number this script had to choose between an
    id nobody can order and an id it cannot measure, and it chose to fail. "44237 -> 2456" says both:
    order the first, measure the second. It is written into the part as `geometry`, exactly as a
    followed redirect already is.
    """
    rows = []
    kind = label = shape = None
    for n, raw in enumerate(open(path, encoding="utf-8"), 1):
        line, _, note = raw.partition("#")
        line, note = line.strip(), note.strip()
        if not line:
            continue
        d = DIRECTIVE.match(line)
        if d:
            kind, label, shape = d.group(1), d.group(2), d.group(3)
            continue
        bits = [b.strip() for b in line.split(",")]
        number, ldraw = bits[0], None
        if "->" in number:
            number, ldraw = [b.strip() for b in number.split("->", 1)]
        qty, color = None, None
        for b in bits[1:]:
            if not b:
                continue
            if b.isdigit():
                qty = int(b)
            else:
                color = b
        rows.append((n, number, ldraw, qty, color, kind, label, shape, note))
    return rows


def build(rows):
    pal = colors()
    parts, problems = [], []
    for lineno, number, ldraw, qty, color, want_kind, want_label, want_shape, note in rows:
        # MEASURE THE FILE THE LINE NAMES, ORDER BY THE NUMBER IT LEADS WITH. Where the line gives
        # only one number the two are the same, and this is what it always did.
        path, target, name = ldparts.resolve(ldraw or number)
        if not path:
            problems.append("line %d: %s could not be resolved in the parts library"
                            % (lineno, ldraw or number)
                            + (" (measuring %s for design %s)" % (ldraw, number) if ldraw else ""))
            cands = suggest(note)
            for cand, desc in cands:
                problems.append("    could it be %s?  %s" % (cand, desc))
            if cands:
                problems.append('    if so, write the line as "%s -> %s" - the design number stays '
                                "the one a builder orders by, the second is only what LDraw measures"
                                % (number, cands[0][0]))
            elif note:
                problems.append("    nothing in the catalog matches %r either - check the number"
                                % note)
            continue
        box = ldparts.bbox(path)
        if not box:
            problems.append("line %d: %s has no measurable geometry" % (lineno, number))
            continue
        minx, maxx, miny, maxy, minz, maxz = box
        w = round((maxx - minx) / ldparts.STUD)
        dd = round((maxz - minz) / ldparts.STUD)
        tall = maxy - miny
        if has_stud(path):
            tall -= STUD_LDU
        h = int(round(tall / PLATE_LDU))
        # AN OBSOLETE MOULD IS REPORTED, NOT SWALLOWED. LDraw marks a file that is not a part in its
        # own right with a leading tilde, and `resolve` only follows "~Moved to" - so a number can
        # redirect onto a file that is merely obsolete and stop there. 3660 does exactly that, landing
        # on 3660a, "~Slope Brick 45 2 x 2 Inverted without Inner Stopper Ring (Obsolete)". The part
        # is still measured, because the geometry is real and the number is the one on the collector's
        # list; but a design number whose mould LDraw calls obsolete is worth a second look before a
        # class orders from it, so it is said out loud rather than carried quietly into the library.
        if name.startswith("~"):
            problems.append("line %d: %s resolves to %s, which LDraw marks obsolete - %s"
                            % (lineno, number, target, " ".join(name.split())))
        kind, shape = classify(name)
        # THE HEADING WINS WHERE IT SPEAKS, classify() answers where it does not - see DIRECTIVE.
        if want_kind:
            kind = want_kind
        if want_shape:
            shape = want_shape
        raw_w = w
        w, dd = footprint(shape, w, dd, resting(path, box))
        part = {"id": number, "name": american(" ".join(name.split())), "kind": kind,
                "w": max(1, w), "d": max(1, dd), "h": max(1, h), "shape": shape}
        # THE LABEL THE MENU BUTTON SHOULD CARRY. The application derives one today by capitalizing
        # the kind, which can only ever produce a single word - "Roundplate" where the catalog says
        # "Round Plate". Written here so the file is right now and the interface can honor it when
        # that pass comes; a field the page does not know is ignored rather than a problem.
        if want_label:
            part["label"] = want_label
        # Only where the footprint was left as it was measured. A slope's w and d are SWAPPED above
        # to turn the ramp across the screen, and a stud position measured in the part's own frame
        # would then be stated against the wrong edge - so a sloped side-stud part, if one is ever
        # ordered, says nothing rather than something misplaced.
        if shape == "rect":
            face = side_studs(path, raw_w)
            if face:
                part["side"] = face
        top = top_studs(path, box, part["w"], part["d"])
        if top is None:
            # NOTHING ON TOP. Said outright, because the page's default is to cover a part in studs
            # and only a kind literally called "tile" was exempt - so a studless part could not be
            # described at all except by lying about what kind it is.
            part["studs"] = False
            top = []
        # AND TURNED WITH THE PART. top_studs measures [across, down] in the part's OWN frame, and a
        # ramped part has had its w and d swapped above to lay the ramp across the profile - so the
        # position was being stated against the wrong pair of edges. 93273 came out with its stud
        # "2.0 down" on a part one stud deep, which is off the piece altogether (Watts, 2026-08-27:
        # "the bow renders as a flat brick with studs on the top").
        # `side` has been guarded against this since it was written; `top` was missed. Swapping is
        # right rather than suppressing, because the swap is known exactly - and it is confirmed by a
        # part measured independently: Glen read 3039's two studs off the photograph as
        # [[0.5,0.5],[0.5,1.5]], and the unswapped measurement is [[0.5,0.5],[1.5,0.5]].
        if top and shape in ("slope", "invslope"):
            top = [[b, a] for a, b in top]
        if top:
            part["top"] = top
        if target.lower() != number.lower():
            # the file the measurements came from - a followed redirect, or the LDraw number the
            # line named outright because LEGO and LDraw number this part differently
            part["geometry"] = target
        if color:
            hit = pal.get(color.lower().replace("_", " "))
            if hit:
                # The CODE is the authority; the name is stored in this project's spelling, since
                # every Sangala surface writes American and LDraw's file writes Grey.
                part["color"] = hit[0].replace("Grey", "Gray")
                part["colorCode"] = hit[1]
            else:
                problems.append("line %d: color %r is not in LDConfig.ldr, so it was left off" % (lineno, color))
        if qty is not None:
            part["qty"] = qty
        parts.append(part)
    return parts, problems


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__.strip().split("\n\n")[1])
    src = argv[1]
    out = argv[argv.index("-o") + 1] if "-o" in argv else os.path.splitext(src)[0] + ".parts"
    rows = read_list(src)
    parts, problems = build(rows)
    lib = {"sangala": "parts", "version": 1,
           "name": os.path.splitext(os.path.basename(src))[0], "parts": parts}
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(lib, f, indent=1)
        f.write("\n")
    print("read %d lines, wrote %d parts to %s" % (len(rows), len(parts), out))
    for p in problems:
        print("  " + p)
    for p in parts:
        print("  %-6s %-38s %s  %d x %d studs, %d plate%s%s"
              % (p["id"], p["name"], p["kind"].ljust(9), p["w"], p["d"], p["h"],
                 "" if p["h"] == 1 else "s",
                 "  x%d %s" % (p.get("qty", 0), p.get("color", "")) if "qty" in p else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
