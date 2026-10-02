import assert from "node:assert/strict";
import { test } from "node:test";
import { itemsForWeather } from "./packing.ts";

test("cold trips get a coat", () => {
	assert.ok(itemsForWeather(-2).includes("coat"));
});
