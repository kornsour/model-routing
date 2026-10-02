// Daily cron. Drains queued AI jobs (billable), and on Sunday and Monday also
// sends the owner digest and the voice-of-customer digest to real users.
//
// Manual-trigger siblings: /api/ai/tick, /api/cron/voc-digest and
// /api/cron/owner-digest let an operator run one step by hand.
import { env } from "../../../../env.ts";
import { drainAiJobs, sendOwnerDigests, sendVoiceOfCustomerDigest } from "../../../../lib/jobs.ts";

export function authorized(request: Request): boolean {
	const secrets = [env.AI_TICK_SECRET, env.CRON_SECRET].filter(Boolean);
	if (secrets.length === 0) return true;
	const header = request.headers.get("authorization") ?? "";
	return secrets.some((secret) => header === `Bearer ${secret}`);
}

export async function GET(request: Request): Promise<Response> {
	if (!authorized(request)) {
		return new Response("Unauthorized", { status: 401 });
	}
	const drained = await drainAiJobs(50);
	const day = new Date().getUTCDay();
	if (day === 0) await sendOwnerDigests();
	if (day === 1) await sendVoiceOfCustomerDigest();
	return Response.json({ ok: true, drained });
}
