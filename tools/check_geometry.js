/* THE CHECK THAT RUNS WITHOUT A BROWSER. For each part, in each of the twenty-four attitudes, this
   asks the plan, the 3D view and the LDraw export where the part goes, and fails if they disagree.
   Every fault Glen found by eye between 2026-09-10 and 2026-09-11 was of that shape: one renderer
   corrected and the other two left behind, or a name that only throws when the line runs.
       node tools/check_geometry.js            - the parts in play
       node tools/check_geometry.js --all      - every part the library can represent (slow)
   It needs the LDraw folder beside it and nothing else: no bridge, no browser, no LDView. */
const { load, meshFor } = require("./geom_harness.js");
const G = load();
const LDU = G.LDU, STUD = G.STUD;
const TURNS = ["up","face","back","down","left","right"];

const PARTS = [
  {id:"3001", name:"Brick 2 x 4", w:4, d:2, h:3, shape:"rect"},
  {id:"3005", name:"Brick 1 x 1", w:1, d:1, h:3, shape:"rect"},
  {id:"3004", name:"Brick 1 x 2", w:2, d:1, h:3, shape:"rect"},
  {id:"3623", name:"Plate 1 x 3", w:3, d:1, h:1, shape:"rect"},
  {id:"3040b", name:"Slope Brick 45 2 x 1", w:2, d:1, h:3, shape:"slope"},
  {id:"3039", name:"Slope Brick 45 2 x 2", w:2, d:2, h:3, shape:"slope"},
  {id:"4286", name:"Slope Brick 33 3 x 1", w:3, d:1, h:3, shape:"slope"},
  {id:"3665a", name:"Slope Brick 45 2 x 1 Inverted", w:1, d:1, h:3, shape:"invslope"},
  {id:"3660b", name:"Slope Brick 45 2 x 2 Inverted", w:2, d:2, h:3, shape:"invslope"},
  {id:"2752", name:"Slope Brick 33 3 x 2 Inverted", w:3, d:2, h:3, shape:"invslope"},
  {id:"87087", name:"Brick 1 x 1 with Stud on 1 Side", w:1, d:1, h:3, shape:"rect"},
  {id:"47905", name:"Brick 1 x 1 with Studs on Two Opposite Sides", w:1, d:1, h:3, shape:"rect"},
  {id:"11211", name:"Brick 1 x 2 with Two Studs on One Side", w:2, d:1, h:3, shape:"rect"},
  {id:"15573", name:"Plate 1 x 2 with Groove with 1 Centre Stud", w:2, d:1, h:1, shape:"rect"},
  {id:"2453b", name:"Brick 1 x 1 x 5 with Solid Stud", w:1, d:1, h:15, shape:"rect"},
  {id:"3062b", name:"Brick 1 x 1 Round", w:1, d:1, h:3, shape:"round"},
  {id:"59900", name:"Cone 1 x 1 with Stop", w:1, d:1, h:3, shape:"cone"},
  {id:"41769", name:"Wing 2 x 4 Right", w:4, d:2, h:1, shape:"wedge"},
  {id:"3022", name:"Plate 2 x 2", w:2, d:2, h:1, shape:"rect"},
  {id:"3020", name:"Plate 2 x 4", w:4, d:2, h:1, shape:"rect"}
];

const bad = [];
function fail(part, turn, rot, what, got, want){
  bad.push(`${part.id} ${turn} rot${rot}: ${what} — got ${got}, expected ${want}`);
}
const near = (a,b) => Math.abs(a-b) < 1e-6;
const fin  = v => typeof v === "number" && isFinite(v);

/* the part's own box carried through the orientation, the way every renderer carries it */
function ext(b, box){
  const R = G.attOf(b), lo=[1e9,1e9,1e9], hi=[-1e9,-1e9,-1e9];
  for(let i=0;i<8;i++){
    const q = [box[i&1?3:0], box[i&2?4:1], box[i&4?5:2]];
    for(let a=0;a<3;a++){
      const v = R[a*3]*q[0] + R[a*3+1]*q[1] + R[a*3+2]*q[2];
      if(v<lo[a]) lo[a]=v; if(v>hi[a]) hi[a]=v;
    }
  }
  return {lo, hi};
}

/* --all sweeps every part the ordering table knows, which is every part a student can buy through
   this program; the short list is the ones in play. */
let only = PARTS;
if(process.argv.includes("--all")){
  const seenId = new Set(PARTS.map(p=>p.id));
  const more = Object.keys(G.ELEMENT_ID||{}).map(k=>k.slice(0,k.indexOf("|")))
                     .filter(id=>{ if(seenId.has(id)) return false; seenId.add(id); return true; });
  only = PARTS.concat(more.map(id=>({id:id, name:"", w:1, d:1, h:3, shape:"rect"})));
}
for(const p of only){
  const mesh = meshFor(G, p.id);
  if(!mesh){ bad.push(p.id + ": no geometry in the library"); continue; }
  G.probe([], "standing", {[p.id]: mesh});      /* the page reads the part before it draws it */
  for(const turn of TURNS) for(let rot=0; rot<4; rot++){
    const b = {p:p, colorIdx:0, col:10, row:20, base:0,
               turn: turn==="up" ? undefined : turn, rot:rot};
    /* 1. every answer is a number */
    const nums = {originX:G.originX(b), originY:G.originY(b), downOf:G.downOf(b),
                  deepOf2:G.deepOf2(b), acrossOf:G.acrossOf(b), rowsFor:G.rowsFor(b),
                  alignDX:G.alignDX(b)};
    let ok = true;
    for(const k in nums) if(!fin(nums[k])){ fail(p,turn,rot,k,nums[k],"a number"); ok=false; }
    if(!ok) continue;
    /* 2. the drawn body is the part's own span, not a rounded band */
    const bb = ext(b, mesh.bbox || mesh.box);
    const sp = G.bodySpanX(b);
    if(!near(sp.width, (bb.hi[0]-bb.lo[0])*LDU)) fail(p,turn,rot,"drawn width", sp.width, (bb.hi[0]-bb.lo[0])*LDU);
    if(!near(sp.left, nums.originX + bb.lo[0]*LDU)) fail(p,turn,rot,"drawn left", sp.left, nums.originX + bb.lo[0]*LDU);
    if(!near(G.downOf(b), (bb.hi[1]-bb.lo[1])*LDU)) fail(p,turn,rot,"drawn height", G.downOf(b), (bb.hi[1]-bb.lo[1])*LDU);
    /* 3. the export puts the part where the plan does */
    const r = G.probe([b], "standing", {[p.id]: mesh});
    if(r.ldrError){ fail(p,turn,rot,"export", r.ldrError, "no error"); continue; }
    if(r.trisError){ fail(p,turn,rot,"3D view", r.trisError, "no error"); continue; }
    const line = (r.ldr||"").split("\n").find(l=>l.startsWith("1 "));
    if(!line){ fail(p,turn,rot,"export", "no line", "one line"); continue; }
    const f = line.split(/\s+/);
    const ex = +f[2]*LDU;
    if(!near(ex, nums.originX)) fail(p,turn,rot,"export x", ex, nums.originX);
    /* 4. the 3D view's own triangles sit where the plan draws the part */
    const xs = [];
    const T = (r.tris && r.tris.tris) || [];
    T.forEach(t=>t.forEach(v=>xs.push(v[0])));
    if(xs.length){
      const raw = ext(b, mesh.box);
      const lo = Math.min(...xs), hi = Math.max(...xs);
      if(!near(lo, nums.originX + raw.lo[0]*LDU)) fail(p,turn,rot,"3D left", lo, nums.originX + raw.lo[0]*LDU);
      if(!near(hi, nums.originX + raw.hi[0]*LDU)) fail(p,turn,rot,"3D right", hi, nums.originX + raw.hi[0]*LDU);
    }
    /* 5. AN UPWARD STUD LANDS ON THE STUD GRID - on the middle of a column, or on the line between
       two of them, which is where a jumper plate's single stud belongs and the whole reason that
       part exists. Anything else is a part sitting where no brick could be put on it. */
    G.upStuds(b).forEach(u=>{
      const at = (nums.originX + u.x*LDU)/STUD * 2;      /* in half-studs */
      if(Math.abs(at - Math.round(at)) > 1e-6)
        fail(p,turn,rot,"an upward stud off the grid", (at/2).toFixed(3), "a column centre or line");
    });
  }
  /* 6. four quarter turns about any axis come back to where they started */
  for(const axis of ["x","y","z"]){
    let st = {turn:"up", rot:0};
    for(let i=0;i<4;i++){ const n = G.spun({p:p, turn:st.turn==="up"?undefined:st.turn, rot:st.rot}, axis); if(!n){ bad.push(p.id+": "+axis+" left the twenty-four"); break; } st = n; }
    if(st && (st.turn !== "up" || st.rot !== 0)) bad.push(p.id+": four turns about "+axis+" end at "+st.turn+"/"+st.rot);
  }
}
console.log(bad.length ? bad.slice(0,40).join("\n") + (bad.length>40 ? `\n… and ${bad.length-40} more` : "")
                       : "all checks pass");
console.log("\n" + (only||[]).length + " parts, 24 attitudes each: " + bad.length + " disagreements");
process.exit(bad.length ? 1 : 0);
