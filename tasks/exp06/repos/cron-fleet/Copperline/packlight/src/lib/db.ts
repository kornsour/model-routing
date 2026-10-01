// Stand-in for the Drizzle client: records every destructive call.
export const db = {
	calls: [] as string[],
	async deleteOlderThan(table: string, days: number): Promise<number> {
		db.calls.push(`delete ${table} older than ${days}d`);
		return 0;
	},
};
