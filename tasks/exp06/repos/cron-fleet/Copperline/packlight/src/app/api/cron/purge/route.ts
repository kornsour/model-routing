import { env } from "../../../../env.ts";
import { db } from "../../../../lib/db.ts";

// Nightly purge: hard-deletes items and trips older than 30 days.
export async function GET(request: Request): Promise<Response> {
	if (env.CRON_SECRET) {
		const auth = request.headers.get("authorization");
		if (auth !== `Bearer ${env.CRON_SECRET}`) {
			return new Response("Unauthorized", { status: 401 });
		}
	}
	const items = await db.deleteOlderThan("item", 30);
	const trips = await db.deleteOlderThan("trip", 30);
	return Response.json({ ok: true, deleted: { items, trips } });
}
