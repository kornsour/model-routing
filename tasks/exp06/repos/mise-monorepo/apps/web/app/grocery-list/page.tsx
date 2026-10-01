import { getWeekPlan } from "@/app/actions/planner";
import { buildGroceryList } from "@/lib/grocery/aggregate";
import { prisma } from "@mise/core/db";
import { ListActions } from "./list-actions";

export default async function GroceryListPage({ searchParams }: { searchParams: { week?: string } }) {
	const plan = await getWeekPlan(searchParams.week);
	const recipes = await prisma.recipe.findMany({
		where: { id: { in: plan.assignments.map((a) => a.recipeId) } },
		include: { ingredients: true },
	});
	const items = buildGroceryList(plan.assignments, recipes);
	return (
		<main>
			<h1>Grocery list</h1>
			<ul>{items.map((i) => <li key={`${i.name}-${i.unit}`}>{i.quantity} {i.unit} {i.name}</li>)}</ul>
			<ListActions items={items} />
			<a href={`/send-to-store?week=${searchParams.week ?? ""}`}>Send to store</a>
		</main>
	);
}
