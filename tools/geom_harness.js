/* Load SangalaBlockDesigner.html's own script in Node, behind stubs for the page it expects, and
   hand back the geometry functions. Nothing here re-implements any of them: the point is to check
   the code that ships, not a transcription of it - every transcription so far has been a second
   source of truth and this exists to stop that. */
const fs = require("fs"), path = require("path");
const ROOT = path.join(__dirname, "..");

function stub(name){
  const f = function(){ return f; };
  return new Proxy(f, {
    get(t,k){
      if(k === Symbol.toPrimitive) return () => 0;
      if(k === "length" || k === "width" || k === "height") return 0;
      if(k === "style" || k === "classList" || k === "dataset") return stub(name+"."+k);
      if(k === "value" || k === "textContent" || k === "innerHTML") return "";
      if(k === "then" || k === "catch") return undefined;      /* not a promise */
      return stub(name+"."+String(k));
    },
    set(){ return true; },
    apply(){ return stub(name+"()"); },
    has(){ return true; }
  });
}

function load(){
  const html = fs.readFileSync(path.join(ROOT, "SangalaBlockDesigner.html"), "utf8");
  const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
  const src = scripts.reduce((a,b)=> a.length>b.length ? a : b);
  const WANT = ["attOf","attCell","spanOf","acrossOf","downOf","deepOf2","rowsFor","originX","originY",
                "bodySpanX","meshMidX","alignDX","upStuds","planStuds","overLeft","overRight","footCols",
                "foot","ldrFlatten","ldrMesh","LDU","STUD","PLATE","LDU_PER_STUD","partYaw","faced",
                "turnOf","rotOf","fineX","fineY","ORIENT","spun","A_TURN","mul3","yawM",
                "ELEMENT_ID","footX","bodyExt","footExt","upStudX","rearB","frontB","parked","boxFor"];
  /* The probe is evaluated in the script's own scope, so it can set the design the three renderers
     read and then call them. That is what makes this a check of the shipping code rather than of a
     copy of it. */
  const tail = "\n;(function(){ const o = {};\n" +
    WANT.map(n=>`try{ o[${JSON.stringify(n)}] = ${n}; }catch(e){}`).join("\n") +
    `\no.probe = function(bs, m, mesh){
       if(mesh) for(const k in mesh) ldrMesh[k] = mesh[k];
       mode = m || "standing"; bricks = bs; selBrick = null; selMulti = [];
       const out = {};
       try { out.ldr = toLdr(); } catch(e){ out.ldrError = e.message; }
       try { out.tris = bricksToTris(); } catch(e){ out.trisError = e.message; }
       return out;
     };\n` +
    "\nglobalThis.__GEOM = o; })();\n";
  const sandbox = {
    document: stub("document"), window: stub("window"), navigator: stub("navigator"),
    localStorage: stub("localStorage"), location: stub("location"),
    requestAnimationFrame: ()=>0, cancelAnimationFrame: ()=>0,
    setTimeout: ()=>0, clearTimeout: ()=>0, setInterval: ()=>0, clearInterval: ()=>0,
    fetch: ()=>({ then(){ return this; }, catch(){ return this; } }),
    Image: function(){ return stub("Image"); }, URL: stub("URL"), Blob: function(){},
    DOMParser: function(){ return stub("DOMParser"); }, alert: ()=>0, console,
    ResizeObserver: function(){ return stub("ResizeObserver"); },
    MutationObserver: function(){ return stub("MutationObserver"); },
    IntersectionObserver: function(){ return stub("IntersectionObserver"); },
    FileReader: function(){ return stub("FileReader"); },
    XMLHttpRequest: function(){ return stub("XMLHttpRequest"); },
    performance: { now: ()=>0 }, matchMedia: ()=>stub("matchMedia"),
    devicePixelRatio: 1, innerWidth: 1200, innerHeight: 800, getComputedStyle: ()=>stub("style")
  };
  const names = Object.keys(sandbox);
  try {
    new Function(...names, src + tail)(...names.map(n=>sandbox[n]));
  } catch(e){
    throw new Error("the page script would not run under the stubs: " + e.message);
  }
  if(!globalThis.__GEOM) throw new Error("no geometry came back");
  return globalThis.__GEOM;
}

/* The parts library, read the way the bridge serves it, so ldrFlatten builds the same mesh the page
   builds. */
const BASE = path.join(ROOT, "LDraw", "ldraw");
const DIRS = ["parts", "p", path.join("parts","s"), path.join("p","48"), path.join("p","8")];
const seen = Object.create(null);
function fileFor(name){
  const key = name.replace(/\\/g,"/").toLowerCase();
  if(key in seen) return seen[key];
  for(const d of DIRS){
    const q = path.join(BASE, d, ...key.split("/"));
    if(fs.existsSync(q)) return seen[key] = fs.readFileSync(q, "utf8");
  }
  return seen[key] = undefined;
}
function gather(name, files, depth){
  const key = name.replace(/\\/g,"/").toLowerCase();
  if(files[key] !== undefined || depth > 24) return;
  const t = fileFor(key);
  files[key] = t === undefined ? "" : t;
  if(t === undefined) return;
  for(const line of t.split("\n")){
    const f = line.trim().split(/\s+/);
    if(f[0] === "1" && f.length >= 15) gather(f.slice(14).join(" "), files, depth+1);
  }
}
function meshFor(G, id){
  const files = {};
  gather(id + ".dat", files, 0);
  return G.ldrFlatten(files, (id + ".dat").toLowerCase());
}
module.exports = { load, meshFor };
