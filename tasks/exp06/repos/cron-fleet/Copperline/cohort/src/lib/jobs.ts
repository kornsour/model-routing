// Stand-ins for the billable and user-facing work the cron routes trigger.
export const effects = {
	calls: [] as string[],
	reset() {
		effects.calls.length = 0;
	},
};

export async function drainAiJobs(limit: number): Promise<number> {
	effects.calls.push(`drainAiJobs(${limit})`);
	return 0;
}

export async function sendOwnerDigests(): Promise<number> {
	effects.calls.push("sendOwnerDigests");
	return 0;
}

export async function sendVoiceOfCustomerDigest(): Promise<number> {
	effects.calls.push("sendVoiceOfCustomerDigest");
	return 0;
}
