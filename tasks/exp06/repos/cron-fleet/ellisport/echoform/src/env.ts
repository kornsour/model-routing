export const env = {
	get CRON_SECRET(): string | undefined {
		return process.env.CRON_SECRET || undefined;
	},
};
