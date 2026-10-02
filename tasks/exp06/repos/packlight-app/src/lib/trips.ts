export type Trip = { id: string; name: string; start: string; end: string };

export async function listTrips(): Promise<Trip[]> {
	return [];
}
