"""Work out the smallest LDraw library that can draw everything Sangala Blocks offers, and track it.

The full library is 24,591 part files and half a gigabyte - reference data that is rightly
git-ignored. But the snapshot feature cannot ship without SOME library beside it, so this walks
every part number the application can place, follows each "~Moved to" redirect and every sub-file
reference down through parts/, parts/s/, p/ and p/48/, and tracks exactly that closure: about 150
files and well under a megabyte.

    python tools/bundle_parts.py           # report what the closure is
    python tools/bundle_parts.py --track   # and `git add -f` it, since LDraw/ is ignored

THE PART NUMBERS ARE READ OUT OF THE PAGE, never listed here. A number typed into this file is one
that stops matching the day a part is added to the menu, and the failure is silent: the brick simply
does not appear in the render.
"""
import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(REPO, "SangalaBlockDesigner.html")

# WHERE IT READS AND WHERE IT SHIPS ARE NOW TWO DIFFERENT PLACES, and keeping them apart is the whole
# of this change. The catalog may sit outside the repository - see ldparts._pick_root - but what the
# application SHIPS must be inside it, or a snapshot cannot be rendered on a machine that has only
# this clone. So the closure is computed against whatever catalog is available and the files it names
# are COPIED into LDraw\ldraw before they are tracked. Where the two are the same folder, which is
# the case with no catalog checked out, the copy is a no-op and this behaves exactly as it did.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldparts

ROOT = ldparts.ROOT                                   # read here
SHIP = os.path.join(REPO, "LDraw", "ldraw")           # ship to here
SEARCH = ["parts", "p", os.path.join("parts", "s"), os.path.join("p", "48")]

# Not parts, but the library cannot be used without them: LDConfig.ldr is where the color codes the
# page writes (15 White, 71 Light Bluish Gray...) are actually defined, and the two CA files are the
# library's own license and readme, which travel with any copy of it.
EXTRAS = ["LDConfig.ldr", "CAlicense.txt", "CAreadme.txt", "Readme.txt"]

# THE PARTS CAN BE PRUNED; THE PRIMITIVES CANNOT. A walk of the references finds every part a design
# can name, and that pruning is worth it - 39 files against 24,591. It does NOT find the primitives
# LDView substitutes as it draws: the logo-bearing stud that puts LEGO on every stud top, and the
# 48-segment versions of the curves. Nothing in the library refers to either, so two attempts at
# guessing which ones to add both produced a render that looked right and was not - the studs alone
# differed, 13,080 pixels of them, against the full library. Shipping every primitive ends the guess:
# measured identical, and 9.6 MB is a small price for a render that cannot silently drift.
# `--verify` is what proved it and is the gate if this is ever narrowed again.
SHIP_ALL_PRIMITIVES = True


def library_ids():
    """Numbers named by any .parts library in the repository.

    THE MENU IS NO LONGER THE WHOLE ANSWER. A library adds parts the page's own tables never held -
    the starter set's tile is the first - and a part that is placed but not bundled renders as
    nothing at all, without an error. So every library that travels with the application is read
    here too, and its parts ship with it.
    """
    ids, alias = set(), {}
    for folder in ("Projects", "Parts"):
        d = os.path.join(REPO, folder)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            # BOTH NAMES, because the application writes ".library" and every file made before it
            # said ".parts" - one format, two spellings, and a library the bundler cannot see is a
            # set of parts that render as nothing at all, silently.
            if not n.lower().endswith((".parts", ".library")):
                continue
            try:
                lib = json.load(open(os.path.join(d, n), encoding="utf-8"))
            except Exception as e:
                print("could not read %s: %s" % (n, e))
                continue
            for p in lib.get("parts", []):
                if p.get("id"):
                    ids.add(str(p["id"]))
                # AND THE FILE IT WAS MEASURED FROM, which is not always the number it is ordered by.
                # A design number LDraw files under a different one - 2752 measured as 3747a, 44237
                # as 2456 - has no file of its own to walk, so the closure reported it missing and
                # would have shipped without its geometry: the part draws as nothing, silently, which
                # is the failure this whole script exists to prevent.
                if p.get("geometry"):
                    ids.add(str(p["geometry"]))
                    alias[str(p["id"])] = str(p["geometry"])
    return ids, alias


def part_ids():
    src = open(HTML, encoding="utf-8").read()
    ids = set()
    kinds = re.search(r"const KINDS = \{.*?\n\};", src, re.S)
    sizes = re.search(r"const SIZES = \{.*?\};", src, re.S)
    for block in (kinds, sizes):
        if not block:
            continue
        for m in re.finditer(r'"(\d{3,6}[a-z]?)"', block.group(0)):
            ids.add(m.group(1))
        for m in re.finditer(r'id:"(\d{3,6}[a-z]?)"', block.group(0)):
            ids.add(m.group(1))
    return sorted(ids)


def locate(name):
    name = name.replace("\\", "/").split("/")[-1].lower()
    if not name.endswith(".dat"):
        name += ".dat"
    for d in SEARCH:
        p = os.path.join(ROOT, d, name)
        if os.path.exists(p):
            return p
    return None


def closure(ids):
    seen, missing = {}, []

    def walk(name):
        # Key on the FILE, not on the spelling. A model names a part as "3023b" and a sub-file
        # reference names it "3023b.dat"; keying on the raw string counted one file twice and
        # reported a closure seven files larger than it is.
        key = name.replace("\\", "/").split("/")[-1].lower()
        if not key.endswith(".dat"):
            key += ".dat"
        if key in seen:
            return
        path = locate(name)
        if not path:
            if name not in missing:
                missing.append(name)
            return
        seen[key] = path
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                t = line.strip()
                if t.startswith("0 ~Moved to "):
                    walk(t.split()[3])
                elif t.startswith("1 "):
                    bits = t.split()
                    if len(bits) >= 15:
                        walk(bits[14])

    for i in ids:
        walk(i)
    return seen, missing


def verify(subset_root):
    """Render the same model against the subset and against the full library, and compare pixels.

    The only trustworthy test of "is this enough": geometry that is missing does not raise an error,
    it just is not drawn. Needs LDView beside the program and the full library still on disk.
    """
    import hashlib
    import tempfile
    try:
        import fitz
    except ImportError:
        print("verify needs pymupdf (python -m pip install pymupdf)")
        return 1
    ldview = os.path.join(REPO, "LDView", "LDView64.exe")
    model = os.path.join(REPO, "Projects", "test.ldr")
    if not (os.path.isfile(ldview) and os.path.isfile(model)):
        print("verify needs LDView\\LDView64.exe and Projects\\test.ldr")
        return 1
    out = []
    for label, root in (("subset", subset_root), ("full", ROOT)):
        png = os.path.join(tempfile.gettempdir(), "bundle_verify_%s.png" % label)
        if os.path.exists(png):
            os.remove(png)
        subprocess.run([ldview, model, "-LDrawDir=" + root, "-SaveSnapshot=" + png,
                        "-SaveWidth=1000", "-SaveHeight=800", "-SaveAlpha=1", "-AutoCrop=1",
                        "-ShowEdges=1", "-ConditionalHighlights=1", "-SaveActualSize=0", "-cg30,45"],
                       check=False)
        if not os.path.exists(png):
            print("%s: LDView produced no image" % label)
            return 1
        out.append(hashlib.sha1(fitz.Pixmap(png).samples).hexdigest())
    same = out[0] == out[1]
    print("subset render: %s" % out[0][:16])
    print("full render:   %s" % out[1][:16])
    print("IDENTICAL" if same else "DIFFERENT - the subset is missing something LDView draws")
    return 0 if same else 1


def main(argv):
    if "--verify" in argv:
        i = argv.index("--verify")
        root = argv[i + 1] if len(argv) > i + 1 else ROOT
        return verify(root)
    menu = part_ids()
    lib, alias = library_ids()
    ids = sorted(set(menu) | lib)
    files, missing = closure(ids)
    # A DESIGN NUMBER WITH NO FILE OF ITS OWN IS NOT MISSING GEOMETRY. LDraw has nothing under 2752
    # or 44237 - it files those parts as 3747a and 2456 - and the library already records which file
    # was measured. Walking the design number still matters, because most of them ARE present as
    # "~Moved to" stubs and the application asks by the number it was given; but where there is no
    # stub and the alias resolved, the part draws perfectly well and saying otherwise would send
    # somebody hunting for a file that has never existed.
    missing = [m for m in missing if not (alias.get(m) and alias[m] not in missing)]
    # only the PARTS come from the closure; every primitive ships (see SHIP_ALL_PRIMITIVES above)
    parts = sorted(p for p in files.values()
                   if os.sep + "parts" + os.sep in p + os.sep)
    prims = []
    for root, _dirs, names in os.walk(os.path.join(ROOT, "p")):
        prims += [os.path.join(root, n) for n in names]
    paths = parts + sorted(prims)
    for e in EXTRAS:
        p = os.path.join(ROOT, e)
        if os.path.exists(p):
            paths.append(p)
    size = sum(os.path.getsize(p) for p in paths)
    print("catalog read from:         %s" % ROOT)
    print("part numbers in the page: %d" % len(menu))
    print("added by .parts libraries: %d  (%s)"
          % (len(lib - set(menu)), ", ".join(sorted(lib - set(menu))) or "none"))
    print("parts needed to draw them: %d  (the library holds 24,591)" % len(parts))
    print("primitives, all of them:   %d" % len(prims))
    print("plus library files:        %s" % ", ".join(EXTRAS))
    print("total:                     %d files, %.1f MB" % (len(paths), size / 1048576.0))
    if missing:
        print("NOT FOUND (the render would silently drop these): %s" % ", ".join(missing))
        return 1
    if "--track" in argv:
        rel, copied = [], 0
        for src in paths:
            inside = os.path.join(SHIP, os.path.relpath(src, ROOT))
            if os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(inside)):
                d = os.path.dirname(inside)
                if not os.path.isdir(d):
                    os.makedirs(d)
                if not (os.path.exists(inside) and os.path.getsize(inside) == os.path.getsize(src)
                        and open(inside, "rb").read() == open(src, "rb").read()):
                    shutil.copyfile(src, inside)
                    copied += 1
            rel.append(os.path.relpath(inside, REPO).replace("\\", "/"))
        if copied:
            print("copied %d file%s from %s into the repository"
                  % (copied, "" if copied == 1 else "s", ROOT))
        # -f because LDraw/ is ignored: the full library stays untracked, this subset does not.
        for i in range(0, len(rel), 200):
            subprocess.run(["git", "-C", REPO, "add", "-f"] + rel[i:i + 200], check=True)
        print("tracked %d files with git add -f" % len(rel))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
