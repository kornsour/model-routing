// Manual tick for the AI job queue. Kept separate from the daily cron so an
// operator can drain a backlog by hand.
import { env } from "../../../../env.ts";
import { drainAiJobs } from "../../../../lib/jobs.ts";

function tickAuthorized(request: Request): boolean {
	const secrets = [env.AI_TICK_SECRET, env.CRON_SECRET].filter(Boolean);
	if (secrets.length === 0) return true;
	const header = request.headers.get("authorization") ?? "";
	return secrets.some((secret) => header === `Bearer ${secret}`);
}

export async function POST(request: Request): Promise<Response> {
	if (!tickAuthorized(request)) {
		return new Response("Unauthorized", { status: 401 });
	}
	const drained = await drainAiJobs(10);
	return Response.json({ ok: true, drained });
}
