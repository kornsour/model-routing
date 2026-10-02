import { getWeekPlan } from "@/app/actions/planner";
import { WeekGrid } from "./week-grid";

export default async function PlannerPage({ searchParams }: { searchParams: { week?: string } }) {
	const plan = await getWeekPlan(searchParams.week);
	return (
		<main>
			<h1>This week</h1>
			<WeekGrid plan={plan} />
		</main>
	);
}
