import { prisma } from "@mise/core/db";
import { requireUser } from "@/lib/auth";

export default async function PlansPage() {
	const user = await requireUser();
	const plans = await prisma.mealPlan.findMany({ where: { userId: user.id }, orderBy: { weekStart: "desc" } });
	return <ul>{plans.map((p) => <li key={p.id}><a href={`/planner?week=${p.weekStart.toISOString()}`}>{p.weekStart.toDateString()}</a></li>)}</ul>;
}
