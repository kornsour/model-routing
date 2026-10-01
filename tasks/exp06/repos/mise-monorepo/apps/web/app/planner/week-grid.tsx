"use client";

import { assignMeal, clearSlot } from "@/app/actions/planner";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SLOTS = ["breakfast", "lunch", "dinner"];

export function WeekGrid({ plan }: { plan: { id: string; assignments: { day: number; slot: string; recipeId: string }[] } }) {
	return (
		<table>
			<tbody>
				{SLOTS.map((slot) => (
					<tr key={slot}>
						{DAYS.map((d, day) => {
							const a = plan.assignments.find((x) => x.day === day && x.slot === slot);
							return (
								<td key={d}>
									{a ? <button onClick={() => clearSlot(plan.id, day, slot)}>{a.recipeId}</button> : <button onClick={() => assignMeal(plan.id, day, slot, prompt("Recipe id") ?? "")}>+</button>}
								</td>
							);
						})}
					</tr>
				))}
			</tbody>
		</table>
	);
}
