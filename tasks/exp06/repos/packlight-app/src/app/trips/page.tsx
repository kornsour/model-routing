import { listTrips } from "../../lib/trips";

export default async function TripsPage() {
	const trips = await listTrips();
	return <ul>{trips.map((t) => <li key={t.id}>{t.name}</li>)}</ul>;
}
