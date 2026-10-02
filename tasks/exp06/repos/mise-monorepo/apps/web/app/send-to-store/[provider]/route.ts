import { NextResponse } from "next/server";
import { getWeekPlan } from "@/app/actions/planner";
import { ADAPTERS } from "@/lib/grocery-adapters";

export async function POST(_req: Request, { params }: { params: { provider: string } }) {
	const adapter = ADAPTERS.find((a) => a.id === params.provider);
	if (!adapter || !adapter.enabled()) return NextResponse.json({ error: "unavailable" }, { status: 404 });
	const plan = await getWeekPlan();
	const result = await adapter.send(plan.assignments.map((a) => ({ name: a.recipeId, quantity: a.servings, unit: "pc" })));
	return result.kind === "link" ? NextResponse.redirect(result.url) : NextResponse.json(result);
}
