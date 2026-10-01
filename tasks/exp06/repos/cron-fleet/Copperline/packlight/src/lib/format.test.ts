import assert from "node:assert/strict";
import { test } from "node:test";
import { plural } from "./format.ts";

test("plural", () => {
	assert.equal(plural(1, "trip"), "1 trip");
	assert.equal(plural(2, "trip"), "2 trips");
});
