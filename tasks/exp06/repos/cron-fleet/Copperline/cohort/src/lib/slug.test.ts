import assert from "node:assert/strict";
import { test } from "node:test";

test("cohort slugs are lowercase", () => {
	assert.equal("Cohort-A".toLowerCase(), "cohort-a");
});
