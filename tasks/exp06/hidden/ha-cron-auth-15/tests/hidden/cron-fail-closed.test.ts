// Hidden grader (exp06 stratum A): every cron route must fail closed.
import assert from "node:assert/strict";
import { test } from "node:test";

import { db as packlightDb } from "../../Copperline/packlight/src/lib/db.ts";
import { GET as packlightPurge } from "../../Copperline/packlight/src/app/api/cron/purge/route.ts";
import { effects } from "../../Copperline/cohort/src/lib/jobs.ts";
import { GET as cohortDaily } from "../../Copperline/cohort/src/app/api/cron/daily/route.ts";
import { GET as cohortVoc } from "../../Copperline/cohort/src/app/api/cron/voc-digest/route.ts";
import { GET as cohortOwner } from "../../Copperline/cohort/src/app/api/cron/owner-digest/route.ts";
import { POST as cohortTick } from "../../Copperline/cohort/src/app/api/ai/tick/route.ts";
import { storage } from "../../ellisport/echoform/src/lib/recordings.ts";
import { GET as echoRetention } from "../../ellisport/echoform/src/app/api/cron/retention-sweep/route.ts";
import { db as binwiseDb } from "../../Copperline/binwise/src/lib/db.ts";
import { GET as binwisePurge } from "../../Copperline/binwise/src/app/api/cron/purge/route.ts";

type Handler = (request: Request) => Promise<Response>;
type Route = { name: string; handler: Handler; method: string; calls: () => number; reset: () => void };

const routes: Route[] = [
	{ name: "packlight purge", handler: packlightPurge, method: "GET", calls: () => packlightDb.calls.length, reset: () => { packlightDb.calls.length = 0; } },
	{ name: "cohort daily", handler: cohortDaily, method: "GET", calls: () => effects.calls.length, reset: () => effects.reset() },
	{ name: "cohort voc-digest", handler: cohortVoc, method: "GET", calls: () => effects.calls.length, reset: () => effects.reset() },
	{ name: "cohort owner-digest", handler: cohortOwner, method: "GET", calls: () => effects.calls.length, reset: () => effects.reset() },
	{ name: "cohort ai/tick", handler: cohortTick, method: "POST", calls: () => effects.calls.length, reset: () => effects.reset() },
	{ name: "echoform retention", handler: echoRetention, method: "GET", calls: () => storage.calls.length, reset: () => { storage.calls.length = 0; } },
	{ name: "binwise purge", handler: binwisePurge, method: "GET", calls: () => binwiseDb.calls.length, reset: () => { binwiseDb.calls.length = 0; } },
];

function setSecrets(cron?: string, tick?: string) {
	if (cron === undefined) delete process.env.CRON_SECRET;
	else process.env.CRON_SECRET = cron;
	if (tick === undefined) delete process.env.AI_TICK_SECRET;
	else process.env.AI_TICK_SECRET = tick;
}

async function call(route: Route, auth?: string): Promise<{ status: number; ran: number }> {
	route.reset();
	const headers: Record<string, string> = auth ? { authorization: auth } : {};
	let status = 500;
	try {
		const res = await route.handler(new Request("http://localhost/x", { method: route.method, headers }));
		status = res.status;
	} catch {
		status = 500; // refusing by throwing still fails closed
	}
	return { status, ran: route.calls() };
}

for (const route of routes) {
	test(`${route.name}: no secret configured is refused`, async () => {
		setSecrets();
		for (const auth of [undefined, "Bearer ", "Bearer undefined", "Bearer anything"]) {
			const { status, ran } = await call(route, auth);
			assert.equal(ran, 0, `${route.name} ran its job with no secret configured (auth=${auth})`);
			assert.ok(status < 200 || status >= 300, `${route.name} answered ${status} with no secret configured`);
		}
	});

	test(`${route.name}: wrong bearer is refused`, async () => {
		setSecrets("s3cret", "t1ck");
		const { status, ran } = await call(route, "Bearer wrong");
		assert.equal(ran, 0);
		assert.ok(status < 200 || status >= 300);
	});

	test(`${route.name}: right CRON_SECRET bearer still runs`, async () => {
		setSecrets("s3cret", "t1ck");
		const { status, ran } = await call(route, "Bearer s3cret");
		assert.ok(status >= 200 && status < 300, `${route.name} refused a valid request (${status})`);
		assert.ok(ran > 0, `${route.name} did not run its job for a valid request`);
	});
}

for (const route of routes.filter((r) => r.name === "cohort daily" || r.name === "cohort ai/tick")) {
	test(`${route.name}: AI_TICK_SECRET bearer still accepted`, async () => {
		setSecrets("s3cret", "t1ck");
		const { status, ran } = await call(route, "Bearer t1ck");
		assert.ok(status >= 200 && status < 300 && ran > 0);
	});
}
