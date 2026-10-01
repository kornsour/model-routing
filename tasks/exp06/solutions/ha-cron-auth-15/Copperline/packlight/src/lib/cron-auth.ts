import { env } from "../env.ts";

// Fail closed: no configured secret, or a header that does not match it, is a
// 401. A cron route that deletes data must never run because a variable was
// forgotten in one environment.
export function cronAuthorized(request: Request): boolean {
	const secret = env.CRON_SECRET;
	if (!secret) return false;
	return request.headers.get("authorization") === `Bearer ${secret}`;
}
