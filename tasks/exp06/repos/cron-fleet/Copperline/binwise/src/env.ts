// Environment, read at access time. CRON_SECRET is optional here so local
// development and CI can run without it; the cron routes refuse requests
// when it is missing.
export const env = {
	get CRON_SECRET(): string | undefined {
		return process.env.CRON_SECRET || undefined;
	},
	get DATABASE_URL(): string {
		return process.env.DATABASE_URL ?? "postgres://localhost/binwise";
	},
};
