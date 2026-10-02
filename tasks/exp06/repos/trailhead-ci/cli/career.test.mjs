// Runs the CLI as a child process, the precedent for testing scripts here.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { test } from "node:test";

test("career CLI echoes its arguments", () => {
	const out = JSON.parse(execFileSync(process.execPath, ["cli/career.mjs", "status"], { encoding: "utf8" }));
	assert.deepEqual(out.args, ["status"]);
});
