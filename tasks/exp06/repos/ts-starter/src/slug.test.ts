import assert from "node:assert/strict";
import { test } from "node:test";
import { slugify } from "./slug.ts";

test("slugify collapses punctuation and trims dashes", () => {
	assert.equal(slugify("  Hello, World!  "), "hello-world");
});
