import { db } from "../../../../lib/db.ts";
import { cronAuthorized } from "../../../../lib/cron-auth.ts";

export async function GET(request: Request): Promise<Response> {
	if (!cronAuthorized(request)) {
		return new Response("Unauthorized", { status: 401 });
	}
	const items = await db.deleteOlderThan("bin_item", 30);
	return Response.json({ ok: true, deleted: { items } });
}
