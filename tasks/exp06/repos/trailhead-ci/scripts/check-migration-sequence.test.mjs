import assert from "node:assert/strict";
import { test } from "node:test";
import { checkSequence } from "./check-migration-sequence.mjs";

test("contiguous migrations pass", () => {
	assert.deepEqual(checkSequence(["0000_init.sql", "0001_users.sql"]), []);
});

test("a gap is reported", () => {
	assert.equal(checkSequence(["0000_init.sql", "0002_x.sql"]).length, 1);
});
