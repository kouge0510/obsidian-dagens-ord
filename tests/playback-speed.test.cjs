const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "src", "playback-speed.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
	compilerOptions: {
		module: ts.ModuleKind.CommonJS,
		target: ts.ScriptTarget.ES2020,
	},
}).outputText;

const sandbox = { module: { exports: {} } };
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled, sandbox, { filename: sourcePath });
const speed = sandbox.module.exports;

assert.deepEqual(Array.from(speed.PLAYBACK_RATES), [0.75, 1, 1.25, 1.5, 2]);
assert.equal(speed.normalizePlaybackRate(0.75), 0.75);
assert.equal(speed.normalizePlaybackRate(0.8), 1);
assert.equal(speed.normalizePlaybackRate(Number.NaN), 1);
assert.equal(speed.nextPlaybackRate(0.75), 1);
assert.equal(speed.nextPlaybackRate(1), 1.25);
assert.equal(speed.nextPlaybackRate(2), 0.75);
assert.equal(speed.nextPlaybackRate(999), 1.25);
assert.equal(speed.formatPlaybackRate(1), "1.0x");
assert.equal(speed.formatPlaybackRate(1.25), "1.25x");

console.log("playback-speed tests passed");
