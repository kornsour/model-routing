import { getWeekPlan } from "@/app/actions/planner";
import { ADAPTERS } from "@/lib/grocery-adapters";

export default async function SendToStorePage() {
	await getWeekPlan();
	return (
		<main>
			<h1>Send to a store</h1>
			<p>Pick a store. We will open it with your list ready to shop.</p>
			<ul>
				{ADAPTERS.map((a) => (
					<li key={a.id}>
						<form action={`/send-to-store/${a.id}`} method="post">
							<button disabled={!a.enabled()}>{a.enabled() ? a.label : `${a.label} (coming soon)`}</button>
						</form>
					</li>
				))}
			</ul>
		</main>
	);
}
