import { cronAuthorized } from "../../../../lib/cron-auth.ts";
import { db } from "../../../../lib/db.ts";

// Nightly purge: hard-deletes items and trips older than 30 days. Fails closed,
// like binwise: an unset CRON_SECRET refuses every request.
export async function GET(request: Request): Promise<Response> {
	if (!cronAuthorized(request)) {
		return new Response("Unauthorized", { status: 401 });
	}
	const items = await db.deleteOlderThan("item", 30);
	const trips = await db.deleteOlderThan("trip", 30);
	return Response.json({ ok: true, deleted: { items, trips } });
}
