// Stand-in for the storage client: records every deletion.
export const storage = {
	calls: [] as string[],
	async deleteRecordingsOlderThan(days: number): Promise<number> {
		storage.calls.push(`delete recordings older than ${days}d`);
		return 0;
	},
};
