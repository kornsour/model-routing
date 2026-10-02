// Manual tick for the AI job queue. Kept separate from the daily cron so an
// operator can drain a backlog by hand.
import { drainAiJobs } from "../../../../lib/jobs.ts";
import { authorized as tickAuthorized } from "../../cron/daily/route.ts";

export async function POST(request: Request): Promise<Response> {
	if (!tickAuthorized(request)) {
		return new Response("Unauthorized", { status: 401 });
	}
	const drained = await drainAiJobs(10);
	return Response.json({ ok: true, drained });
}
