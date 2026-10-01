// Server environment, validated at access time. The shape mirrors the Zod
// schema this file replaced: required keys throw when missing, optional keys
// return undefined.

function required(name: string): string {
	const value = process.env[name];
	if (!value) throw new Error(`missing required env var ${name}`);
	return value;
}

function optional(name: string): string | undefined {
	return process.env[name] || undefined;
}

export const env = {
	get DATABASE_URL() {
		return process.env.DATABASE_URL ?? "postgres://localhost/cohort";
	},
	get RESEND_API_KEY() {
		return optional("RESEND_API_KEY");
	},
	get AI_TICK_SECRET() {
		return optional("AI_TICK_SECRET");
	},
	// Optional so `next build` and CI work without it.
	get CRON_SECRET() {
		return optional("CRON_SECRET");
	},
	get APP_URL() {
		return process.env.APP_URL ?? "http://localhost:3000";
	},
};

export { required };
