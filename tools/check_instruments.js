// Instrument checker: syntax + id cross-check + stub execution.
// Usage: node check_instruments.js <file.html> [...]
const fs = require('fs');
const vm = require('vm');

function extractScripts(html) {
  const scripts = [];
  const re = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = re.exec(html)) !== null) scripts.push(m[1]);
  return scripts;
}
function extractIds(html) {
  const ids = new Set();
  const re = /\bid="([^"]+)"/g;
  let m;
  while ((m = re.exec(html)) !== null) ids.add(m[1]);
  return ids;
}

function makeCtx2d() {
  const grad = { addColorStop() {} };
  return new Proxy({}, { get: (t, k) => {
    if (k === 'createLinearGradient' || k === 'createRadialGradient') return () => grad;
    if (k === 'measureText') return () => ({ width: 10 });
    if (k === 'getImageData' || k === 'createImageData') return () => ({ data: new Uint8ClampedArray(4) });
    if (k === 'canvas') return { width: 800, height: 600 };
    if (typeof k === 'string') return (...a) => undefined;
    return undefined;
  }, set: () => true });
}
function makeGL() {
  return new Proxy({}, { get: (t, k) => {
    if (k === 'canvas') return { width: 800, height: 600 };
    if (k === 'getExtension') return () => ({});
    if (k === 'getParameter') return () => 4096;
    if (k === 'getShaderParameter' || k === 'getProgramParameter') return () => true;
    if (k === 'getShaderInfoLog' || k === 'getProgramInfoLog') return () => '';
    if (k === 'createShader' || k === 'createProgram' || k === 'createBuffer' ||
        k === 'createTexture' || k === 'createFramebuffer' || k === 'createRenderbuffer' ||
        k === 'getUniformLocation') return () => ({});
    if (k === 'getAttribLocation' || k === 'getError') return () => 0;
    if (typeof k === 'string') {
      // WebGL constants are numbers
      if (/^[A-Z][A-Z0-9_]*$/.test(k)) return 1;
      return (...a) => undefined;
    }
    return undefined;
  }, set: () => true });
}
function makeElement(id) {
  const el = {
    id, width: 800, height: 600, clientWidth: 800, clientHeight: 600,
    style: {}, textContent: '', innerHTML: '', value: '',
    children: [], dataset: {},
    getContext: (kind) => kind && kind.includes('webgl') ? makeGL() : makeCtx2d(),
    addEventListener() {}, removeEventListener() {},
    getComputedStyle: () => new Proxy({ getPropertyValue: () => '' }, { get: (t, k) => k in t ? t[k] : '' }),
    getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600, right: 800, bottom: 600 }),
    appendChild(c) { el.children.push(c); return c; },
    setAttribute() {}, getAttribute: () => null, querySelector: () => makeElement('q'),
    querySelectorAll: () => [], classList: { add() {}, remove() {}, toggle() {} },
  };
  return el;
}

for (const file of process.argv.slice(2)) {
  const html = fs.readFileSync(file, 'utf8');
  const name = file.split('/').pop();
  const scripts = extractScripts(html);
  const ids = extractIds(html);
  const problems = [];
  // 1. syntax
  scripts.forEach((s, i) => {
    try { new vm.Script(s, { filename: `${name}#script${i}` }); }
    catch (e) { problems.push(`SYNTAX script#${i}: ${e.message.split('\n')[0]}`); }
  });
  // 2. id cross-check
  const referenced = new Set();
  for (const s of scripts) {
    let m; const re = /getElementById\(\s*['"]([^'"]+)['"]\s*\)/g;
    while ((m = re.exec(s)) !== null) referenced.add(m[1]);
    const re2 = /querySelector\(\s*['"]#([A-Za-z0-9_-]+)['"]\s*\)/g;
    while ((m = re2.exec(s)) !== null) referenced.add(m[1]);
  }
  for (const id of referenced) if (!ids.has(id)) problems.push(`MISSING ELEMENT: #${id} referenced but not in markup`);
  // 3. stub execution
  const elements = new Map();
  const getEl = (id) => { if (!elements.has(id)) elements.set(id, makeElement(id)); return elements.get(id); };
  let rafCount = 0;
  const sandbox = {
    console, Math, JSON, Date, Array, Object, Number, String, Boolean, RegExp, Error, Map, Set, Promise, Float32Array, Uint8Array, Uint16Array, Int32Array, parseInt, parseFloat, isNaN, setTimeout: (fn) => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
    innerWidth: 1200, innerHeight: 800, devicePixelRatio: 1,
    location: { href: 'http://x/' + name, search: '' },
    navigator: { userAgent: 'stub' },
    performance: { now: () => 1000 },
    requestAnimationFrame: (fn) => { if (rafCount++ < 5) { try { fn(1000 + rafCount * 16); } catch (e) { problems.push(`RAF FRAME: ${e.message}`); } } return rafCount; },
    addEventListener() {}, removeEventListener() {},
    getComputedStyle: () => new Proxy({ getPropertyValue: () => '' }, { get: (t, k) => k in t ? t[k] : '' }),
    getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
    document: {
      getElementById: (id) => ids.has(id) || referenced.has(id) ? getEl(id) : null,
      querySelector: (sel) => sel.startsWith('#') ? getEl(sel.slice(1)) : makeElement('q'),
      querySelectorAll: () => [],
      createElement: (tag) => makeElement(tag),
      body: makeElement('body'), documentElement: makeElement('html'),
      addEventListener() {},
    },
  };
  sandbox.window = sandbox; sandbox.globalThis = sandbox;
  sandbox.document.defaultView = sandbox;
  for (const [i, s] of scripts.entries()) {
    try { vm.runInNewContext(s, sandbox, { filename: `${name}#script${i}`, timeout: 5000 }); }
    catch (e) { problems.push(`RUNTIME script#${i}: ${e.message.split('\n')[0]}`); }
  }
  console.log(`== ${name}: ${problems.length ? problems.join(' | ') : 'CLEAN (syntax, ids, stub-exec + 5 frames)'}`);
}
