// Environment, read at access time. CRON_SECRET is optional so local
// development and CI can run without it.
export const env = {
	get CRON_SECRET(): string | undefined {
		return process.env.CRON_SECRET || undefined;
	},
	get DATABASE_URL(): string {
		return process.env.DATABASE_URL ?? "postgres://localhost/packlight";
	},
};
