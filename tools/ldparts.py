"""Read the LDraw parts library and report what a part actually is.

Sangala Block Designer plans a LEGO kit, so every part it offers must carry a real
design number and a real footprint. Both are in the library sitting beside the
application - so they are READ, never typed from memory and never checked by hand.

    python tools/ldparts.py find "Wedge"          # search descriptions
    python tools/ldparts.py show 3005 3004 3023   # resolve, name and measure

What it knows about the format:
  * a part's FIRST line is its name:  "0 Brick  1 x  1"
  * a superseded number answers      "0 ~Moved to 3023b"  and must be followed
  * line type 1 is a sub-part reference: 1 <colour> x y z a b c d e f g h <file>
    with the 3x4 matrix in row-major order; line types 2-5 carry raw points
  * geometry is measured recursively through parts/, parts/s/, p/ and p/48/
  * 1 LDU = 0.4 mm, stud pitch 20 LDU, plate 8 LDU, brick 24 LDU; +Y is DOWN,
    so a part's own origin sits at the TOP of its body
"""
import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# WHERE THE CATALOG IS. It lived in exactly one place - LDraw\ldraw beside the application - and
# that is still the first place looked, because the subset the repository ships must travel with it
# or a snapshot cannot be rendered offline. But the FULL catalog is 19,000 parts of somebody else's
# data, versioned on its own schedule, and putting it in this repository would be permanent, would
# slow every git command on Windows, and would land in Glen's history if this ever merges upstream
# (Watts, 2026-08-27, choosing a separate repository over all three). So it may also sit elsewhere:
#   1. wherever SANGALA_LDRAW points - set this to the catalog repository's ldraw folder
#   2. LDraw\ldraw inside this repository - the bundled subset, which is what ships
#   3. SangalaLDraw\ldraw beside this repository - a catalog clone checked out as a sibling
# A folder only counts if it actually holds parts, so an empty or half-cloned one falls through to
# the next rather than silently answering "NOT IN LIBRARY" for everything.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pick_root():
    here = os.path.join(_REPO, "LDraw", "ldraw")
    tries = [os.environ.get("SANGALA_LDRAW"), here,
             os.path.join(os.path.dirname(_REPO), "SangalaLDraw", "ldraw")]
    best, most = here, -1
    for t in tries:
        if not t:
            continue
        d = os.path.join(t, "parts")
        if not os.path.isdir(d):
            continue
        n = sum(1 for f in os.listdir(d) if f.endswith(".dat"))
        if n > most:                # the fullest catalog wins, so a clone beats the bundled subset
            best, most = t, n
    return best


ROOT = _pick_root()
SEARCH = ["parts", "p", os.path.join("parts", "s"), os.path.join("p", "48")]
LDU_MM, STUD, PLATE = 0.4, 20.0, 8.0


def locate(name):
    name = name.replace("\\", "/").split("/")[-1].lower()
    if not name.endswith(".dat"):
        name += ".dat"
    for d in SEARCH:
        p = os.path.join(ROOT, d, name)
        if os.path.exists(p):
            return p
    return None


def first_line(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("0 "):
                return line[2:].strip()
            if line:
                return ""
    return ""


def resolve(number, seen=None):
    """Follow ~Moved to / ~Renamed redirects to the file that holds the geometry."""
    seen = seen or set()
    path = locate(number)
    if not path or number.lower() in seen:
        return path, number, first_line(path) if path else ""
    seen.add(number.lower())
    desc = first_line(path)
    low = desc.lower()
    if low.startswith("~moved to") or low.startswith("~renamed to"):
        target = desc.split()[-1]
        return resolve(target, seen)
    return path, number, desc


IDENT = (1.0, 0, 0,  0, 1.0, 0,  0, 0, 1.0,  0.0, 0.0, 0.0)   # 9 rotation terms, then 3 of translation


def _mul(M, S):
    """M applied AFTER S, both in the 9+3 form above."""
    r = [0.0] * 12
    for i in range(3):
        for j in range(3):
            r[i * 3 + j] = M[i * 3] * S[j] + M[i * 3 + 1] * S[3 + j] + M[i * 3 + 2] * S[6 + j]
        r[9 + i] = M[i * 3] * S[9] + M[i * 3 + 1] * S[10] + M[i * 3 + 2] * S[11] + M[9 + i]
    return tuple(r)


_TEXT = {}


def _lines(path):
    key = os.path.normcase(path)
    if key not in _TEXT:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            _TEXT[key] = f.read().split("\n")
    return _TEXT[key]


def _walk(path, M, depth, chain, take):
    """Every vertex of a part, in the part's own frame, through all its sub-files."""
    key = os.path.normcase(path)
    if depth > 12 or key in chain:
        return
    chain = chain + (key,)
    for line in _lines(path):
        t = line.split()
        if not t:
            continue
        if t[0] == "1" and len(t) >= 15:
            try:
                v = [float(x) for x in t[2:14]]
            except ValueError:
                continue
            sub = locate(" ".join(t[14:]))
            if not sub:
                continue
            S = (v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10], v[11], v[0], v[1], v[2])
            _walk(sub, _mul(M, S), depth + 1, chain, take)
        elif t[0] in ("2", "3", "4", "5"):
            n = {"2": 2, "3": 3, "4": 4, "5": 4}[t[0]]
            try:
                v = [float(x) for x in t[2:2 + 3 * n]]
            except ValueError:
                continue
            for i in range(n):
                x, y, z = v[3 * i], v[3 * i + 1], v[3 * i + 2]
                take(M[0] * x + M[1] * y + M[2] * z + M[9],
                     M[3] * x + M[4] * y + M[5] * z + M[10],
                     M[6] * x + M[7] * y + M[8] * z + M[11])


def bbox(path, depth=0, seen=None):
    """Bounding box in LDU as (minx,maxx,miny,maxy,minz,maxz), or None.

    MEASURED FROM THE VERTICES, NOT FROM A SUB-PART'S BOX. This used to recurse, take the box a
    sub-file reported, and transform its eight corners. That is exact only where the placement is
    axis-aligned - and every curved part in the library is built from primitives placed at an angle,
    where the box around a rotated box is bigger than the box around the shape.

    It measured Plate 2 x 2 Round at 2.61 studs across instead of 2.00, which parts_library rounded
    to 3, and Slope Brick Curved 4 x 1 Double at 8 studs long and 14.49 plates tall instead of 4 and
    about 2 - that one places a quarter cylinder through a sheared matrix, so the corner box bears
    almost no relation to the ramp it draws (Watts, 2026-08-27, reading a library where a 1 x 4 bow
    had become eight studs long). A 1 x 1 round part came out right throughout, which is what made
    the fault look like nothing at all: it is one full cylinder placed square, so its corners
    transform exactly.

    Walking the vertices costs re-reading a sub-file once per placement rather than once per part -
    a stud referenced eight times is now walked eight times, which is the point, since each sits
    somewhere different. `_TEXT` keeps the file contents so that costs no extra reading.
    """
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3

    def take(x, y, z):
        for i, v in enumerate((x, y, z)):
            if v < lo[i]:
                lo[i] = v
            if v > hi[i]:
                hi[i] = v

    _walk(path, IDENT, depth, (), take)
    if lo[0] == float("inf"):
        return None
    return (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])


def show(numbers):
    print("%-9s %-10s %-38s %-14s %s" % ("asked", "geometry", "name", "studs (w x d)", "height"))
    for n in numbers:
        path, resolved, desc = resolve(n)
        if not path:
            print("%-9s %-10s NOT IN LIBRARY" % (n, "-"))
            continue
        got = os.path.basename(path)[:-4]
        b = bbox(path)
        if not b:
            print("%-9s %-10s %-38s %s" % (n, got, desc[:38], "no geometry"))
            continue
        w, d = (b[1] - b[0]) / STUD, (b[5] - b[4]) / STUD
        h = (b[3] - b[2]) / PLATE
        print("%-9s %-10s %-38s %-14s %.2f plates (%.1f mm)"
              % (n, got, desc[:38], "%.2f x %.2f" % (w, d), h, (b[3] - b[2]) * LDU_MM))


def _squash(s):
    """One space between words, lowercased - so a typed term need not reproduce LDraw's padding."""
    return " ".join(s.lower().split())


def catalog(quiet=False):
    """(number, description) for every part - from parts.lst, else from an index built once.

    READING EVERY PART FILE IS NOT A SEARCH, IT IS A SWEEP. Thirty-nine files in the repository's
    bundled subset, about 19,000 in the real library, each a separate open inspected by whatever the
    machine runs. It does return, eventually, which is worse than failing: twice now a search has
    looked like a hang (Watts, 2026-08-27).

    Some LDraw distributions ship parts.lst, one line per part, holding exactly what a search needs.
    Mine assumed every distribution did. Where it is absent the sweep happens ONCE and is written to
    parts.index beside it, so only the first search after an install pays for it. The index is
    rebuilt when the parts folder has been touched more recently than the index, which catches a
    library that has been updated underneath it. LDraw/ is git-ignored, so neither file is ever
    committed by accident.
    """
    lst = os.path.join(ROOT, "parts.lst")
    if os.path.exists(lst):
        rows = _read_index(lst)
        if rows:
            return rows
    d = os.path.join(ROOT, "parts")
    cache = os.path.join(ROOT, "parts.index")
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(d):
        rows = _read_index(cache)
        if rows:
            return rows
    names = sorted(n for n in os.listdir(d) if n.endswith(".dat"))
    if not quiet and len(names) > 500:
        sys.stderr.write("reading %d part descriptions, once - the index is kept in %s\n"
                         % (len(names), os.path.basename(cache)))
        sys.stderr.flush()
    rows = [(n[:-4], first_line(os.path.join(d, n))) for n in names]
    try:
        with open(cache, "w", encoding="utf-8", newline="\n") as f:
            for num, desc in rows:
                f.write("%s.dat %s\n" % (num, " ".join(desc.split())))
    except OSError:
        pass          # a read-only library is still searchable, just never fast
    return rows


def _read_index(path):
    """parts.lst and parts.index are the same shape: a file name, then its description."""
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            bits = line.strip().split(None, 1)
            if len(bits) == 2 and bits[0].lower().endswith(".dat"):
                out.append((bits[0][:-4], bits[1]))
    return out


def find(term, limit=25):
    """Search descriptions. EVERY WORD MUST APPEAR, in any order.

    It matched one contiguous substring before, which meant the searcher had to guess the exact
    phrasing AND the exact word order LDraw chose. "2 x 3 inverted" found nothing while the part sat
    there, because a description is written "Slope Brick 45  2 x  3 Inverted" and one stray word in
    between - or the size written the other way round - defeats a substring. Falling back to a single
    broad word then returned the cap and no way to narrow it (Watts, 2026-08-27: "Searching for
    inverted returned 25 blocks").

    So the term is split and every piece must be somewhere in the description: "inverted 45 3" finds
    it whichever way round the size is written, and adding a word narrows rather than breaks. The
    total is reported even when the list is capped, so a search that is still too broad says so
    instead of looking like the whole answer.
    """
    want = _squash(term).split()
    hits, shown = 0, 0
    for num, desc in catalog():
        low = desc.lower()
        if low.startswith("~moved to") or low.startswith("~renamed"):
            continue
        # A TILDE IS TWO DIFFERENT STATEMENTS AND ONLY ONE IS NOISE: a redirect stub is skipped just
        # above, but an OBSOLETE MOULD is marked the same way and is a real part with real geometry -
        # the crane orders 3660, which is one. Skipping both hid every obsolete part from the search.
        hay = _squash(desc)
        if all(w in hay for w in want):
            hits += 1
            if shown < limit:
                print("  %-10s %s" % (num, " ".join(desc.split())))
                shown += 1
    if not hits:
        print("  nothing matched %r" % term)
    elif hits > shown:
        print("  ... %d matches in all; add a word to narrow it" % hits)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
    elif sys.argv[1] == "find":
        find(" ".join(sys.argv[2:]))
    else:
        show(sys.argv[2:])
