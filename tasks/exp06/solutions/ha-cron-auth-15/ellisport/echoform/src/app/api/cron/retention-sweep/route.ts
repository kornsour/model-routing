import { env } from "../../../../env.ts";
import { storage } from "../../../../lib/recordings.ts";

// Retention: recordings are deleted 90 days after upload.
function isCronRequest(request: Request): boolean {
	const secret = env.CRON_SECRET;
	if (!secret) return false; // fail closed: unset means nobody is authorized
	return request.headers.get("authorization") === `Bearer ${secret}`;
}

export async function GET(request: Request): Promise<Response> {
	if (!isCronRequest(request)) {
		return new Response("Unauthorized", { status: 401 });
	}
	const deleted = await storage.deleteRecordingsOlderThan(90);
	return Response.json({ ok: true, deleted });
}
