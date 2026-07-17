import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {createRequire} from "node:module";
import {tmpdir} from "node:os";
import path from "node:path";
import {test} from "node:test";
import {fileURLToPath, pathToFileURL} from "node:url";
import vm from "node:vm";
import {mkdtemp, rm} from "node:fs/promises";

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const OUT = path.join(ROOT, "l4_showcase", "out");
const STORE_PATH = path.join(ROOT, "l4_showcase", "src", "s3_trace_store.js");
const api = require(STORE_PATH);
const MANIFEST = JSON.parse(await readFile(
  path.join(OUT, "s3_trace_manifest.json"), "utf8"
));
const BASE_URL = pathToFileURL(OUT + path.sep).href;
globalThis.window = globalThis;

function clone(value) { return JSON.parse(JSON.stringify(value)); }

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.dataset = {};
    this.hidden = false;
    this.textContent = "";
    this.listeners = {};
    this.removed = false;
  }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  setAttribute(name, value) { this[name] = value; }
  remove() { this.removed = true; }
}

class FakeDocument {
  constructor(baseURI = BASE_URL, transform = null, delayMs = 0) {
    this.baseURI = baseURI;
    this.transform = transform;
    this.delayMs = delayMs;
    this.head = {appendChild: script => this._appendScript(script)};
  }
  createElement(tagName) { return new FakeElement(tagName); }
  _appendScript(script) {
    const execute = async () => {
      try {
        const filename = fileURLToPath(script.src);
        let source = await readFile(filename, "utf8");
        if (this.transform) source = await this.transform(source, script, filename);
        vm.runInThisContext(source, {filename});
        if (script.onload) script.onload();
      } catch (error) {
        if (script.onerror) script.onerror(error);
      }
    };
    if (this.delayMs) setTimeout(execute, this.delayMs);
    else setImmediate(execute);
    return script;
  }
}

function makeStore(overrides = {}) {
  return new api.S3TraceStore({
    root: globalThis,
    document: overrides.document || new FakeDocument(),
    manifest: overrides.manifest || clone(MANIFEST),
    baseUrl: overrides.baseUrl || BASE_URL,
    cacheLimit: overrides.cacheLimit || 3,
    cryptoProvider: Object.prototype.hasOwnProperty.call(overrides, "cryptoProvider")
      ? overrides.cryptoProvider : globalThis.crypto,
    resourceDisposer: overrides.resourceDisposer,
    errorHost: overrides.errorHost,
    onError: overrides.onError
  });
}

function parseTraceScript(source) {
  const prefix = "window.__S3_TRACE_REGISTER__(";
  assert.ok(source.startsWith(prefix) && source.endsWith(");\n"));
  const body = source.slice(prefix.length, -3);
  const comma = body.indexOf(",");
  return {traceId: JSON.parse(body.slice(0, comma)), trace: JSON.parse(body.slice(comma + 1))};
}

test("semantic v1 matches manifest and fallback SHA-256 is correct", async () => {
  const abc = new TextEncoder().encode("abc");
  assert.equal(
    api.sha256Fallback(abc),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
  );
  assert.deepEqual(api.semanticEncodeV1(1), api.semanticEncodeV1(1.0));
  assert.notDeepEqual(api.semanticEncodeV1(0), api.semanticEncodeV1(-0));
  for (const invalid of [NaN, Infinity, 2 ** 53, () => 1]) {
    assert.throws(() => api.semanticEncodeV1(invalid), api.S3TraceError);
  }
  const cycle = {}; cycle.self = cycle;
  assert.throws(() => api.semanticEncodeV1(cycle), {code: "SEMANTIC_CYCLE"});

  const entry = MANIFEST.entries[0];
  const source = await readFile(path.join(OUT, entry.file), "utf8");
  const {trace} = parseTraceScript(source);
  assert.equal(await api.semanticRuntimeHashV1(trace, null),
    entry.semantic_runtime_sha256_v1);
});

test("manifest rejects missing combinations, remote scripts and malformed hashes", () => {
  const missing = clone(MANIFEST);
  missing.entries.pop(); missing.entry_count -= 1;
  assert.throws(() => api.validateManifest(missing), {code: "MANIFEST_COUNT"});
  const remote = clone(MANIFEST);
  remote.entries[0].file = "https://example.com/trace.js";
  assert.throws(() => api.validateManifest(remote), {code: "MANIFEST_ENTRY"});
  const badHash = clone(MANIFEST);
  badHash.entries[0].semantic_runtime_sha256_v1 = "bad";
  assert.throws(() => api.validateManifest(badHash), {code: "MANIFEST_INTEGRITY"});
});

test("base URL accepts local file/same-origin loopback and rejects every network escape", async () => {
  for (const remote of [
    "https://cdn.example.invalid/assets/",
    "http://example.invalid/assets/",
    "//cdn.example.invalid/assets/",
    "file://server/share/"
  ]) {
    assert.throws(() => makeStore({baseUrl: remote}), {code: "BASE_URL_PROTOCOL"});
  }
  const localDocument = new FakeDocument("http://127.0.0.1:7788/src/page.html");
  const local = makeStore({
    document: localDocument,
    baseUrl: "http://127.0.0.1:7788/out/"
  });
  local.destroy();
  assert.throws(() => makeStore({
    document: localDocument,
    baseUrl: "http://127.0.0.1:7799/out/"
  }), {code: "BASE_URL_PROTOCOL"});

  const mutated = makeStore();
  mutated.baseUrl = "https://cdn.example.invalid/assets/";
  await assert.rejects(mutated.load(MANIFEST.entries[0].trace_id),
    {code: "BASE_URL_PROTOCOL"});
  assert.equal(mutated.pendingSlots.size, 0);
  assert.equal(mutated.scripts.size, 0);
  assert.equal(mutated.cacheInfo().size, 0);
  mutated.destroy();
});

test("all 45 file traces load under file URL and LRU retains only three", async () => {
  const disposed = [];
  const reports = [];
  const store = makeStore({
    resourceDisposer: traceId => disposed.push(traceId),
    onError: report => reports.push(report)
  });
  try {
    for (const entry of MANIFEST.entries) {
      const trace = await store.load(entry.trace_id);
      assert.equal(trace.meta.trace_id, entry.trace_id);
      assert.equal(trace.semantic_runtime_sha256_v1,
        entry.semantic_runtime_sha256_v1);
    }
    assert.equal(reports.length, 0);
    assert.equal(store.cacheInfo().size, 3);
    assert.deepEqual(store.cacheInfo().ids,
      MANIFEST.entries.slice(-3).map(entry => entry.trace_id));
    assert.equal(disposed.length, 42);
    assert.equal(Object.keys(globalThis.__S3_TRACE_PAYLOADS__).length, 3);
    const last = globalThis.__S3_TRACE_PAYLOADS__[MANIFEST.entries.at(-1).trace_id];
    assert.throws(() => store.assertComparisonAllowed(last, "排行"),
      {code: "COMPARISON_BLOCKED"});
  } finally { store.destroy(); }
});

test("LRU touch protects the first trace and evicts the second on load four", async () => {
  const disposed = [];
  const store = makeStore({resourceDisposer: traceId => disposed.push(traceId)});
  const ids = MANIFEST.entries.slice(0, 4).map(entry => entry.trace_id);
  try {
    await store.load(ids[0]);
    await store.load(ids[1]);
    await store.load(ids[2]);
    await store.load(ids[0]);
    await store.load(ids[3]);
    assert.deepEqual(store.cacheInfo().ids, [ids[2], ids[0], ids[3]]);
    assert.deepEqual(disposed, [ids[1]]);
    assert.equal(globalThis.__S3_TRACE_PAYLOADS__[ids[1]], undefined);
  } finally { store.destroy(); }
});

test("missing script remains visible for three retries, leaves no residue, then recovers", async () => {
  const manifest = clone(MANIFEST);
  const entry = manifest.entries[0];
  const host = new FakeElement("div");
  const reports = [];
  const temp = await mkdtemp(path.join(tmpdir(), "s3-trace-missing-"));
  const missingBase = pathToFileURL(temp + path.sep).href;
  const store = makeStore({
    manifest, baseUrl: missingBase, errorHost: host,
    onError: report => reports.push(report)
  });
  try {
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      await assert.rejects(store.load(entry.trace_id, {force: true}), {code: "SCRIPT_LOAD"});
      assert.equal(store.cacheInfo().size, 0);
      assert.equal(Object.keys(globalThis.__S3_TRACE_PAYLOADS__).length, 0);
      assert.equal(store.pendingSlots.size, 0);
    }
    assert.equal(reports.length, 3);
    assert.equal(reports[2].attempt, 3);
    assert.match(reports[2].combo, /Tier 1 \/ uniform \/ seq/);
    assert.equal(host.hidden, false);
    assert.equal(host.children[0].children.at(-1).textContent, "重试该组合");
    store.baseUrl = BASE_URL;
    const trace = await store.lastError.retry();
    assert.equal(trace.meta.trace_id, entry.trace_id);
    assert.equal(host.hidden, true);
  } finally {
    store.destroy();
    await rm(temp, {recursive: true, force: true});
  }
});

test("bad schema, deep payload mutation, duplicate registration and swapped script fail closed", async t => {
  const first = MANIFEST.entries[0];
  const cases = [
    {
      name: "schema",
      code: "TRACE_SCHEMA",
      transform: source => source.replace(
        '"schema_version":"s3-dynamic-trace-v2"',
        '"schema_version":"s3-dynamic-trace-vX"'
      )
    },
    {
      name: "deep mutation with old hashes",
      code: "SEMANTIC_HASH",
      transform: source => source.replace('"queue_depth_waiting":0', '"queue_depth_waiting":999')
    },
    {
      name: "bad declared hash",
      code: "HASH_DECLARATION",
      transform: source => source.replace(
        first.semantic_runtime_sha256_v1, "0".repeat(64)
      )
    },
    {
      name: "duplicate registration",
      code: "REGISTER_DUPLICATE",
      transform: source => source + source
    }
  ];
  for (const item of cases) {
    await t.test(item.name, async () => {
      const store = makeStore({document: new FakeDocument(BASE_URL, item.transform)});
      try {
        await assert.rejects(store.load(first.trace_id), {code: item.code});
        assert.equal(store.cacheInfo().size, 0);
        assert.equal(Object.keys(globalThis.__S3_TRACE_PAYLOADS__).length, 0);
      } finally { store.destroy(); }
    });
  }
  await t.test("swapped script", async () => {
    const swappedSource = await readFile(
      path.join(OUT, MANIFEST.entries[1].file), "utf8"
    );
    const store = makeStore({
      document: new FakeDocument(BASE_URL, () => swappedSource)
    });
    try {
      await assert.rejects(store.load(MANIFEST.entries[0].trace_id),
        {code: "REGISTER_MISSING"});
      assert.equal(store.cacheInfo().size, 0);
    } finally { store.destroy(); }
  });
});

test("comparability guard rejects even a self-consistent forged runtime hash", async () => {
  const manifest = clone(MANIFEST);
  const entry = manifest.entries[0];
  const source = await readFile(path.join(OUT, entry.file), "utf8");
  const parsed = parseTraceScript(source);
  parsed.trace.comparability.s1_matrix_same_parameterization = true;
  parsed.trace.comparability.ui_rule = "allow_merge";
  const forgedHash = await api.semanticRuntimeHashV1(parsed.trace, null);
  parsed.trace.semantic_runtime_sha256_v1 = forgedHash;
  entry.semantic_runtime_sha256_v1 = forgedHash;

  const forgedSource =
    `window.__S3_TRACE_REGISTER__(${JSON.stringify(parsed.traceId)},${JSON.stringify(parsed.trace)});\n`;
  const store = makeStore({
    manifest,
    document: new FakeDocument(BASE_URL, () => forgedSource)
  });
  try {
    await assert.rejects(store.load(entry.trace_id), {code: "COMPARABILITY_GUARD"});
    assert.equal(store.cacheInfo().size, 0);
  } finally {
    store.destroy();
  }
});

test("concurrent loads stay isolated and destroy rejects an in-flight script", async () => {
  const disposed = [];
  const store = makeStore({resourceDisposer: traceId => disposed.push(traceId)});
  const ids = MANIFEST.entries.slice(0, 4).map(entry => entry.trace_id);
  try {
    const traces = await Promise.all(ids.map(traceId => store.load(traceId)));
    assert.deepEqual(traces.map(trace => trace.meta.trace_id), ids);
    assert.equal(store.cacheInfo().size, 3);
    assert.equal(disposed.length, 1);
  } finally { store.destroy(); }

  const slow = makeStore({document: new FakeDocument(BASE_URL, null, 80)});
  const pending = slow.load(ids[0]);
  slow.destroy();
  await assert.rejects(pending, {code: "STORE_DESTROYED"});
  assert.equal(slow.pendingSlots.size, 0);
  assert.equal(slow.scripts.size, 0);
  await assert.rejects(slow.load(ids[0]), {code: "STORE_DESTROYED"});
});
