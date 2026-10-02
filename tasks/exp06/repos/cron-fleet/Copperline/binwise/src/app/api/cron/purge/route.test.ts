import assert from "node:assert/strict";
import { test } from "node:test";
import { db } from "../../../../lib/db.ts";
import { GET } from "./route.ts";

const url = "http://localhost/api/cron/purge";

test("purge refuses when CRON_SECRET is unset", async () => {
	delete process.env.CRON_SECRET;
	db.calls.length = 0;
	const res = await GET(new Request(url, { headers: { authorization: "Bearer anything" } }));
	assert.equal(res.status, 401);
	assert.equal(db.calls.length, 0);
});

test("purge runs with the right bearer token", async () => {
	process.env.CRON_SECRET = "s3cret";
	db.calls.length = 0;
	const res = await GET(new Request(url, { headers: { authorization: "Bearer s3cret" } }));
	assert.equal(res.status, 200);
	assert.equal(db.calls.length, 1);
	delete process.env.CRON_SECRET;
});
