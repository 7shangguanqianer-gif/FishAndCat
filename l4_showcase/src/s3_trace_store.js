(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) module.exports = api;
  root.S3TraceStore = api.S3TraceStore;
  root.S3TraceIntegrity = {
    semanticEncodeV1: api.semanticEncodeV1,
    semanticRuntimeHashV1: api.semanticRuntimeHashV1,
    sha256Fallback: api.sha256Fallback
  };
})(typeof window !== "undefined" ? window : globalThis, function (defaultRoot) {
  "use strict";

  const TRACE_SCHEMA = "s3-dynamic-trace-v2";
  const MANIFEST_SCHEMA = "s3-trace-manifest-v2";
  const HASH_FIELD = "semantic_runtime_sha256_v1";
  const JS_SAFE_INTEGER_MAX = Number.MAX_SAFE_INTEGER;
  const EXPECTED_TIERS = [1, 2, 3];
  const EXPECTED_PROFILES = ["uniform", "skew", "heavy"];
  const EXPECTED_MODES = ["seq", "near", "score", "awra", "AUTO"];
  const SHA256_K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ]);

  class S3TraceError extends Error {
    constructor(code, message, details) {
      super(message);
      this.name = "S3TraceError";
      this.code = code;
      this.details = details || {};
    }
  }

  function codePointCompare(left, right) {
    const a = Array.from(left, ch => ch.codePointAt(0));
    const b = Array.from(right, ch => ch.codePointAt(0));
    const count = Math.min(a.length, b.length);
    for (let index = 0; index < count; index += 1) {
      if (a[index] !== b[index]) return a[index] - b[index];
    }
    return a.length - b.length;
  }

  function semanticEncodeV1(value) {
    const bytes = [];
    const encoder = new TextEncoder();
    const active = new WeakSet();

    function pushLength(length) {
      if (!Number.isSafeInteger(length) || length < 0 || length > 0xffffffff) {
        throw new S3TraceError("SEMANTIC_LENGTH", "语义编码长度超出 uint32 契约");
      }
      bytes.push((length >>> 24) & 255, (length >>> 16) & 255,
        (length >>> 8) & 255, length & 255);
    }

    function encode(item) {
      if (item === null) {
        bytes.push(0x00);
      } else if (item === false) {
        bytes.push(0x01);
      } else if (item === true) {
        bytes.push(0x02);
      } else if (typeof item === "number") {
        if (!Number.isFinite(item)) {
          throw new S3TraceError("SEMANTIC_NUMBER", "trace 含 NaN 或 Infinity");
        }
        if (Number.isInteger(item) && Math.abs(item) > JS_SAFE_INTEGER_MAX) {
          throw new S3TraceError("SEMANTIC_INTEGER", "trace 整数超出 JavaScript 安全范围");
        }
        const raw = new ArrayBuffer(8);
        new DataView(raw).setFloat64(0, item, false);
        bytes.push(0x03, ...new Uint8Array(raw));
      } else if (typeof item === "string") {
        const raw = encoder.encode(item);
        bytes.push(0x04);
        pushLength(raw.length);
        bytes.push(...raw);
      } else if (Array.isArray(item)) {
        if (active.has(item)) throw new S3TraceError("SEMANTIC_CYCLE", "trace 含循环数组");
        active.add(item);
        bytes.push(0x05);
        pushLength(item.length);
        item.forEach(encode);
        active.delete(item);
      } else if (item && typeof item === "object") {
        const proto = Object.getPrototypeOf(item);
        if (proto !== Object.prototype && proto !== null) {
          throw new S3TraceError("SEMANTIC_OBJECT", "trace 含非纯 JSON 对象");
        }
        if (active.has(item)) throw new S3TraceError("SEMANTIC_CYCLE", "trace 含循环对象");
        active.add(item);
        const keys = Object.keys(item).sort(codePointCompare);
        bytes.push(0x06);
        pushLength(keys.length);
        keys.forEach(key => {
          encode(key);
          encode(item[key]);
        });
        active.delete(item);
      } else {
        throw new S3TraceError("SEMANTIC_TYPE", `trace 含不支持的类型：${typeof item}`);
      }
    }

    encode(value);
    return Uint8Array.from(bytes);
  }

  function sha256Fallback(input) {
    const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
    const bitLength = bytes.length * 8;
    const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
    const data = new Uint8Array(paddedLength);
    data.set(bytes);
    data[bytes.length] = 0x80;
    const view = new DataView(data.buffer);
    view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000), false);
    view.setUint32(paddedLength - 4, bitLength >>> 0, false);

    const state = new Uint32Array([
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ]);
    const words = new Uint32Array(64);
    const rotate = (value, count) => (value >>> count) | (value << (32 - count));

    for (let offset = 0; offset < data.length; offset += 64) {
      for (let index = 0; index < 16; index += 1) {
        words[index] = view.getUint32(offset + index * 4, false);
      }
      for (let index = 16; index < 64; index += 1) {
        const x = words[index - 15];
        const y = words[index - 2];
        const s0 = rotate(x, 7) ^ rotate(x, 18) ^ (x >>> 3);
        const s1 = rotate(y, 17) ^ rotate(y, 19) ^ (y >>> 10);
        words[index] = (words[index - 16] + s0 + words[index - 7] + s1) >>> 0;
      }
      let a = state[0], b = state[1], c = state[2], d = state[3];
      let e = state[4], f = state[5], g = state[6], h = state[7];
      for (let index = 0; index < 64; index += 1) {
        const sum1 = rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25);
        const choose = (e & f) ^ (~e & g);
        const temp1 = (h + sum1 + choose + SHA256_K[index] + words[index]) >>> 0;
        const sum0 = rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22);
        const majority = (a & b) ^ (a & c) ^ (b & c);
        const temp2 = (sum0 + majority) >>> 0;
        h = g; g = f; f = e; e = (d + temp1) >>> 0;
        d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
      }
      state[0] = (state[0] + a) >>> 0;
      state[1] = (state[1] + b) >>> 0;
      state[2] = (state[2] + c) >>> 0;
      state[3] = (state[3] + d) >>> 0;
      state[4] = (state[4] + e) >>> 0;
      state[5] = (state[5] + f) >>> 0;
      state[6] = (state[6] + g) >>> 0;
      state[7] = (state[7] + h) >>> 0;
    }
    return Array.from(state, value => value.toString(16).padStart(8, "0")).join("");
  }

  async function sha256Hex(bytes, cryptoProvider) {
    const provider = cryptoProvider === undefined ? defaultRoot.crypto : cryptoProvider;
    if (provider && provider.subtle && typeof provider.subtle.digest === "function") {
      const digest = await provider.subtle.digest("SHA-256", bytes);
      return Array.from(new Uint8Array(digest), value =>
        value.toString(16).padStart(2, "0")).join("");
    }
    return sha256Fallback(bytes);
  }

  async function semanticRuntimeHashV1(trace, cryptoProvider) {
    const payload = {};
    Object.keys(trace).forEach(key => {
      if (key !== "payload_sha256" && key !== HASH_FIELD) payload[key] = trace[key];
    });
    return sha256Hex(semanticEncodeV1(payload), cryptoProvider);
  }

  function traceIdFor(tier, profile, strategyMode) {
    return `t${Number(tier)}_${String(profile)}_${String(strategyMode).toLowerCase()}`;
  }

  function localAssetUrl(rawUrl, documentBase) {
    let asset;
    let page;
    try {
      page = new URL(documentBase);
      asset = new URL(rawUrl, page);
    } catch (error) {
      throw new S3TraceError("BASE_URL_PROTOCOL", "trace base URL 非法", {cause: error});
    }
    const loopback = hostname => ["localhost", "127.0.0.1", "[::1]", "::1"]
      .includes(String(hostname).toLowerCase());
    if (asset.username || asset.password) {
      throw new S3TraceError("BASE_URL_PROTOCOL", "trace URL 禁止携带账号信息");
    }
    if (asset.protocol === "file:") {
      if (page.protocol !== "file:" || (asset.hostname && asset.hostname !== "localhost")) {
        throw new S3TraceError("BASE_URL_PROTOCOL", "只允许当前本机 file: trace");
      }
      return asset;
    }
    if ((asset.protocol === "http:" || asset.protocol === "https:") &&
        (page.protocol === "http:" || page.protocol === "https:") &&
        loopback(asset.hostname) && loopback(page.hostname) &&
        asset.origin === page.origin) {
      return asset;
    }
    throw new S3TraceError(
      "BASE_URL_PROTOCOL",
      "trace 只允许本机 file: 或与页面同源的 loopback HTTP(S)"
    );
  }

  function validateManifest(manifest) {
    if (!manifest || manifest.schema_version !== MANIFEST_SCHEMA) {
      throw new S3TraceError("MANIFEST_SCHEMA", "trace manifest schema 不匹配");
    }
    if (!Array.isArray(manifest.entries) || manifest.entries.length !== 45 ||
        manifest.entry_count !== 45) {
      throw new S3TraceError("MANIFEST_COUNT", "trace manifest 必须恰含 45 条组合");
    }
    const ids = new Set(manifest.entries.map(entry => entry.trace_id));
    if (ids.size !== manifest.entries.length) {
      throw new S3TraceError("MANIFEST_DUPLICATE", "trace manifest 含重复 trace_id");
    }
    const expectedIds = new Set();
    EXPECTED_TIERS.forEach(tier => EXPECTED_PROFILES.forEach(profile =>
      EXPECTED_MODES.forEach(mode => expectedIds.add(traceIdFor(tier, profile, mode)))));
    if (ids.size !== expectedIds.size ||
        Array.from(expectedIds).some(traceId => !ids.has(traceId))) {
      throw new S3TraceError("MANIFEST_COVERAGE", "trace manifest 未完整覆盖 3×3×5 组合");
    }
    const sameArray = (left, right) => Array.isArray(left) &&
      left.length === right.length && left.every((value, index) => value === right[index]);
    if (!sameArray(manifest.tiers, EXPECTED_TIERS) ||
        !sameArray(manifest.profiles, EXPECTED_PROFILES) ||
        !sameArray(manifest.ui_modes, EXPECTED_MODES) ||
        manifest.trace_schema_version !== TRACE_SCHEMA || manifest.sim_only !== true) {
      throw new S3TraceError("MANIFEST_AXES", "trace manifest 轴定义或 sim 边界不匹配");
    }
    const hashPattern = /^[0-9a-f]{64}$/;
    manifest.entries.forEach(entry => {
      const expectedId = traceIdFor(entry.tier, entry.profile, entry.strategy_mode);
      if (entry.trace_id !== expectedId ||
          entry.file !== `s3_traces/${entry.trace_id}.js`) {
        throw new S3TraceError("MANIFEST_ENTRY", `非法 trace entry：${entry.trace_id}`);
      }
      if (!hashPattern.test(entry.payload_sha256 || "") ||
          !hashPattern.test(entry.file_sha256 || "") ||
          !hashPattern.test(entry[HASH_FIELD] || "") ||
          !Number.isInteger(entry.bytes) || entry.bytes < 1 || entry.bytes > 800 * 1024) {
        throw new S3TraceError("MANIFEST_INTEGRITY", `trace entry 完整性字段非法：${entry.trace_id}`);
      }
    });
    const policy = manifest.comparability_policy || {};
    if (policy.s1_matrix_same_parameterization !== false ||
        policy.ui_rule !== "do_not_compare_or_merge") {
      throw new S3TraceError("MANIFEST_COMPARABILITY", "S1 参数隔离守门缺失");
    }
  }

  class S3TraceStore {
    constructor(options) {
      const opts = options || {};
      this.root = opts.root || defaultRoot;
      this.document = opts.document || this.root.document;
      this.manifest = opts.manifest || this.root.S3_TRACE_MANIFEST;
      validateManifest(this.manifest);
      if (!this.document || !this.document.createElement || !this.document.head) {
        throw new S3TraceError("DOCUMENT_REQUIRED", "trace store 需要可注入 script 的 document");
      }
      this.baseUrl = localAssetUrl(
        opts.baseUrl || new URL("../out/", this.document.baseURI).href,
        this.document.baseURI
      ).href;
      this.cacheLimit = opts.cacheLimit ?? 3;
      if (!Number.isInteger(this.cacheLimit) || this.cacheLimit < 1) {
        throw new S3TraceError("CACHE_LIMIT", "cacheLimit 必须为正整数");
      }
      this.cryptoProvider = Object.prototype.hasOwnProperty.call(opts, "cryptoProvider")
        ? opts.cryptoProvider : undefined;
      this.onError = typeof opts.onError === "function" ? opts.onError : function () {};
      this.resourceDisposer = typeof opts.resourceDisposer === "function"
        ? opts.resourceDisposer : function () {};
      this.errorHost = opts.errorHost || null;
      this.entries = new Map(this.manifest.entries.map(entry => [entry.trace_id, entry]));
      this.cache = new Map();
      this.inflight = new Map();
      this.pendingSlots = new Map();
      this.scripts = new Map();
      this.attempts = new Map();
      this.registry = Object.create(null);
      this.disposalErrors = [];
      this.destroyed = false;
      this.previousRegister = this.root.__S3_TRACE_REGISTER__;
      this.registerHook = (traceId, payload) => this._register(traceId, payload);
      this.root.__S3_TRACE_REGISTER__ = this.registerHook;
      this.root.__S3_TRACE_PAYLOADS__ = this.registry;
      this.lastError = null;
    }

    _register(traceId, payload) {
      const slot = this.pendingSlots.get(traceId);
      if (!slot) return;
      slot.count += 1;
      if (slot.count === 1) slot.payload = payload;
      else slot.duplicate = true;
    }

    _entryFor(query) {
      const traceId = typeof query === "string"
        ? query
        : traceIdFor(query.tier, query.profile,
          query.strategy_mode === undefined ? query.mode : query.strategy_mode);
      const entry = this.entries.get(traceId);
      if (!entry) {
        throw new S3TraceError("TRACE_NOT_FOUND", `manifest 中没有组合 ${traceId}`, {traceId});
      }
      return entry;
    }

    _touch(traceId) {
      const value = this.cache.get(traceId);
      this.cache.delete(traceId);
      this.cache.set(traceId, value);
      return value;
    }

    _drop(traceId) {
      if (!this.cache.has(traceId)) {
        delete this.registry[traceId];
        return;
      }
      const payload = this.cache.get(traceId);
      this.cache.delete(traceId);
      delete this.registry[traceId];
      try { this.resourceDisposer(traceId, payload); }
      catch (error) { this.disposalErrors.push({traceId, error}); }
    }

    _put(traceId, payload) {
      if (this.cache.has(traceId)) this._drop(traceId);
      this.cache.set(traceId, payload);
      this.registry[traceId] = payload;
      while (this.cache.size > this.cacheLimit) {
        this._drop(this.cache.keys().next().value);
      }
    }

    async _validate(entry, trace) {
      if (!trace || typeof trace !== "object") {
        throw new S3TraceError("TRACE_PAYLOAD", "script 未注册有效 trace 对象");
      }
      if (!trace.meta || trace.meta.trace_id !== entry.trace_id) {
        throw new S3TraceError("TRACE_ID_MISMATCH", "trace id 与请求组合不一致");
      }
      if (trace.schema_version !== TRACE_SCHEMA || entry.schema_version !== TRACE_SCHEMA) {
        throw new S3TraceError("TRACE_SCHEMA", "trace schema 不匹配");
      }
      if (trace.sim_only !== true || entry.sim_only !== true) {
        throw new S3TraceError("SIM_BOUNDARY", "trace 缺少 sim-only 边界");
      }
      if (trace.meta.tier !== entry.tier || trace.meta.profile !== entry.profile ||
          trace.meta.strategy_mode !== entry.strategy_mode) {
        throw new S3TraceError("TRACE_COMBINATION", "trace Tier/画像/算法与 manifest 不一致");
      }
      if (trace.payload_sha256 !== entry.payload_sha256 ||
          trace[HASH_FIELD] !== entry[HASH_FIELD]) {
        throw new S3TraceError("HASH_DECLARATION", "trace hash 声明与 manifest 不一致");
      }
      const computed = await semanticRuntimeHashV1(trace, this.cryptoProvider);
      if (computed !== entry[HASH_FIELD] || computed !== trace[HASH_FIELD]) {
        throw new S3TraceError("SEMANTIC_HASH", "浏览器重算的 trace 语义 hash 不一致");
      }
      const guard = trace.comparability || {};
      if (guard.s1_matrix_same_parameterization !== false ||
          guard.ui_rule !== "do_not_compare_or_merge") {
        throw new S3TraceError("COMPARABILITY_GUARD", "trace 缺少 S1 参数隔离守门");
      }
      const reference = trace.stats && trace.stats.multi_seed_source;
      const locked = this.manifest.matrix_reference;
      if (!reference || !locked ||
          reference.manifest_sha256 !== locked.manifest_sha256 ||
          reference.sha256 !== locked.sha256 ||
          reference.detail_sha256 !== locked.detail_sha256 ||
          reference.params_sha256 !== locked.params_sha256) {
        throw new S3TraceError("MATRIX_REFERENCE", "trace 的 S1 引用与 bundle 不一致");
      }
      return trace;
    }

    _inject(entry) {
      return new Promise((resolve, reject) => {
        let scriptUrl;
        try {
          scriptUrl = localAssetUrl(
            new URL(entry.file, this.baseUrl).href,
            this.document.baseURI
          );
        } catch (error) {
          reject(error);
          return;
        }
        const slot = {count: 0, payload: null, duplicate: false};
        this.pendingSlots.set(entry.trace_id, slot);
        const script = this.document.createElement("script");
        script.async = true;
        script.src = scriptUrl.href;
        if (script.dataset) script.dataset.s3TraceId = entry.trace_id;
        let settled = false;
        const cleanup = () => {
          this.pendingSlots.delete(entry.trace_id);
          this.scripts.delete(script);
          if (typeof script.remove === "function") script.remove();
        };
        const fail = error => {
          if (settled) return;
          settled = true;
          cleanup();
          reject(error);
        };
        this.scripts.set(script, {
          traceId: entry.trace_id,
          cancel: () => fail(new S3TraceError("STORE_DESTROYED", "trace store 已销毁"))
        });
        script.onerror = () => fail(
          new S3TraceError("SCRIPT_LOAD", `无法加载 ${entry.file}`)
        );
        script.onload = async () => {
          if (settled) return;
          try {
            if (slot.duplicate || slot.count > 1) {
              throw new S3TraceError("REGISTER_DUPLICATE", "trace script 重复注册同一 id");
            }
            if (slot.count !== 1) {
              throw new S3TraceError("REGISTER_MISSING", "trace script 已执行但没有注册请求 id");
            }
            const validated = await this._validate(entry, slot.payload);
            if (this.destroyed) {
              throw new S3TraceError("STORE_DESTROYED", "trace store 已销毁");
            }
            settled = true;
            cleanup();
            resolve(validated);
          } catch (error) {
            fail(error);
          }
        };
        try { this.document.head.appendChild(script); }
        catch (error) {
          fail(new S3TraceError("SCRIPT_APPEND", `无法注入 ${entry.file}`, {cause: error}));
        }
      });
    }

    _renderError(report) {
      const host = this.errorHost;
      if (!host || !this.document.createElement) return;
      const box = this.document.createElement("div");
      box.className = "s3-trace-error";
      box.setAttribute && box.setAttribute("role", "alert");
      const title = this.document.createElement("strong");
      title.textContent = `加载失败 · ${report.combo}`;
      const detail = this.document.createElement("span");
      detail.textContent = ` ${report.error.message}（${report.error.code}）`;
      const button = this.document.createElement("button");
      button.type = "button";
      button.textContent = "重试该组合";
      button.addEventListener("click", async () => {
        button.disabled = true;
        try { await report.retry(); } catch (_reported) {}
        finally { button.disabled = false; }
      });
      box.append(title, detail, button);
      if (typeof host.replaceChildren === "function") host.replaceChildren(box);
      else { host.textContent = ""; host.appendChild(box); }
      host.hidden = false;
    }

    _clearError() {
      if (!this.errorHost) return;
      if (typeof this.errorHost.replaceChildren === "function") {
        this.errorHost.replaceChildren();
      } else this.errorHost.textContent = "";
      this.errorHost.hidden = true;
    }

    _report(entry, error) {
      const wrapped = error instanceof S3TraceError
        ? error
        : new S3TraceError("TRACE_LOAD", error && error.message ? error.message : String(error));
      const combo = `Tier ${entry.tier} / ${entry.profile} / ${entry.strategy_mode}`;
      const report = {
        error: wrapped,
        entry,
        combo,
        attempt: this.attempts.get(entry.trace_id) || 0,
        retry: () => this.load(entry.trace_id, {force: true})
      };
      this.lastError = report;
      if (!this.destroyed) {
        this._renderError(report);
        try { this.onError(report); } catch (_ignored) {}
      }
      return wrapped;
    }

    load(query, options) {
      if (this.destroyed) {
        return Promise.reject(new S3TraceError("STORE_DESTROYED", "trace store 已销毁"));
      }
      let entry;
      try { entry = this._entryFor(query); }
      catch (error) { return Promise.reject(error); }
      const force = Boolean(options && options.force);
      if (!force && this.cache.has(entry.trace_id)) {
        return Promise.resolve(this._touch(entry.trace_id));
      }
      if (!force && this.inflight.has(entry.trace_id)) return this.inflight.get(entry.trace_id);
      if (force) this._drop(entry.trace_id);
      this.attempts.set(entry.trace_id, (this.attempts.get(entry.trace_id) || 0) + 1);
      const request = this._inject(entry)
        .then(trace => {
          this._put(entry.trace_id, trace);
          this.lastError = null;
          this._clearError();
          return trace;
        })
        .catch(error => {
          delete this.registry[entry.trace_id];
          if (error && error.code === "STORE_DESTROYED") throw error;
          throw this._report(entry, error);
        })
        .finally(() => this.inflight.delete(entry.trace_id));
      this.inflight.set(entry.trace_id, request);
      return request;
    }

    assertComparisonAllowed(trace, purpose) {
      const guard = trace && trace.comparability;
      if (!guard || guard.s1_matrix_same_parameterization !== true ||
          guard.ui_rule === "do_not_compare_or_merge") {
        throw new S3TraceError(
          "COMPARISON_BLOCKED",
          `禁止将当前代表性回放用于${purpose || "聚合、排行或 regret"}`
        );
      }
      return true;
    }

    cacheInfo() {
      return {size: this.cache.size, ids: Array.from(this.cache.keys())};
    }

    release(traceId) { this._drop(traceId); }

    destroy() {
      if (this.destroyed) return;
      this.destroyed = true;
      Array.from(this.cache.keys()).forEach(traceId => this._drop(traceId));
      Array.from(this.scripts.values()).forEach(record => record.cancel());
      this.scripts.clear();
      this.pendingSlots.clear();
      if (this.root.__S3_TRACE_REGISTER__ === this.registerHook) {
        if (this.previousRegister === undefined) delete this.root.__S3_TRACE_REGISTER__;
        else this.root.__S3_TRACE_REGISTER__ = this.previousRegister;
      }
      if (this.root.__S3_TRACE_PAYLOADS__ === this.registry) {
        delete this.root.__S3_TRACE_PAYLOADS__;
      }
    }
  }

  return {
    S3TraceStore,
    S3TraceError,
    semanticEncodeV1,
    semanticRuntimeHashV1,
    sha256Fallback,
    traceIdFor,
    validateManifest,
    TRACE_SCHEMA,
    MANIFEST_SCHEMA,
    HASH_FIELD,
    localAssetUrl
  };
});
