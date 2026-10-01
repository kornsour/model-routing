import { sendVoiceOfCustomerDigest } from "../../../../lib/jobs.ts";
import { authorized } from "../daily/route.ts";

export async function GET(request: Request): Promise<Response> {
	if (!authorized(request)) {
		return new Response("Unauthorized", { status: 401 });
	}
	const sent = await sendVoiceOfCustomerDigest();
	return Response.json({ ok: true, sent });
}
