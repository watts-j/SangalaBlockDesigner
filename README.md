# Sangala Blocks — plan a LEGO kit from a design

A browser tool for planning a model in real LEGO bricks. The outline of a figure
designed in **Sangala Studio** is brought in as a **frame** — a guide, not geometry —
and the student builds that figure by placing catalog bricks against it, choosing
every part by hand. Each brick carries the design number it is ordered by, so a
finished design is also its own parts list.

One self-contained HTML file. No install, no server, no admin rights, no internet
after the first run. Built for the same schools as Sangala Studio and Sangala Mosaic.

## Source files
- **SangalaBlockDesigner.html** — the whole application: menu bar, Toolbar, parts
  panel, the plan view, the 3D view, and the file handling.
- **SangalaBlockDesignerLauncher.cs** — the Desktop launcher. A real program rather
  than a script, because managed school Windows blocks a `.cmd` and allows an exe;
  it opens the page in the default browser.
- **Build SangalaBlockDesigner Launcher.cmd** — compiles it with the .NET compiler
  already in Windows, embedding `Crane.ico`.
- **Create Desktop Shortcut.cmd** — puts a "Sangala Blocks" icon on the Desktop.
- **tools/ldparts.py** — resolves a design number against the LDraw library, follows
  a retired number to its replacement, and measures the part.
- **tools/sizes_from_ldraw.py** — rewrites the application's size table from that
  library, so no dimension is ever typed by hand.
- **tools/frame_from_model.py** — turns a Sangala Studio `.model` into the built-in
  frame data.
- **tools/make_icon.py** — builds `Crane.ico` from the crane mosaic.

## Build & run
1. Run `Build SangalaBlockDesigner Launcher.cmd` (only needed if the exe is missing).
2. Run `Create Desktop Shortcut.cmd` once.
3. Double-click the **Sangala Blocks** icon; the page opens in your browser.

`Documents/` carries the installation instructions and the parts-library design.

## Conventions
- Geometry follows LEGO, not a drawing grid: a stud is **8 mm**, a plate 3.2 mm, a
  brick 9.6 mm. Bricks snap to the stud lattice.
- Two ways to build: a **standing** figure, seen from the side with studs up, and a
  **relief**, seen face-on with each layer one plate proud of the one behind.
- A design's placement is held apart from its geometry, exactly as Sangala Studio
  holds `offx`/`offy`: the frame, the bricks and the lattice are laid down together,
  so a brick always lands on the outline it is placed against.
- Nothing is placed automatically. The student picks every part — that is the point
  of the tool.

## The parts library
The LDraw library (24,591 parts) is **not** in this repository; it is reference data,
not source. Fetch it beside the application with:

    curl -sL -o LDraw/complete.zip https://library.ldraw.org/library/updates/complete.zip

`Documents/Adding LEGO Blocks` describes the format and how a list of parts becomes a
library the application can import.

## Related
- [Sangala Studio](https://github.com/GlenBull/SangalaStudio) — die cutter control and
  2D/3D design; the source of the frames used here.
- [Sangala Mosaic](https://github.com/GlenBull/SangalaMosaic) — a photograph as a
  mosaic of LEGO tiles.

## License
CC0 1.0 Universal — see `LICENSE`. Sangala Studio and Sangala Mosaic are the same.

## Checking the geometry without a browser

`node tools/check_geometry.js` puts every part in the ordering table into each of the twenty-four
attitudes and asks the plan, the 3D view and the LDraw export where it goes. It fails if the three
disagree, if any of them throws, or if a part's upward studs land off the stud grid. `--all` sweeps
the whole table; with no flag it takes the parts that have been in question.

It runs the application's own code — `tools/geom_harness.js` loads `SangalaBlockDesigner.html`'s
script behind stubs for the page — so it checks what ships rather than a copy of it. It needs the
LDraw folder beside it and nothing else: no bridge, no browser, no LDView.
