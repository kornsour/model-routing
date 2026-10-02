"use server";

import { prisma } from "@mise/core/db";
import { requireUser } from "@/lib/auth";

function weekStartOf(iso?: string): Date {
	const d = iso ? new Date(iso) : new Date();
	const day = (d.getUTCDay() + 6) % 7;
	d.setUTCDate(d.getUTCDate() - day);
	d.setUTCHours(0, 0, 0, 0);
	return d;
}

export async function getWeekPlan(week?: string) {
	const user = await requireUser();
	const weekStart = weekStartOf(week);
	return prisma.mealPlan.upsert({
		where: { userId_weekStart: { userId: user.id, weekStart } },
		create: { userId: user.id, weekStart },
		update: {},
		include: { assignments: true },
	});
}

export async function assignMeal(planId: string, day: number, slot: string, recipeId: string, servings = 2) {
	await requireUser();
	await prisma.mealAssignment.upsert({
		where: { planId_day_slot: { planId, day, slot } },
		create: { planId, day, slot, recipeId, servings },
		update: { recipeId, servings },
	});
}

export async function clearSlot(planId: string, day: number, slot: string) {
	await requireUser();
	await prisma.mealAssignment.delete({ where: { planId_day_slot: { planId, day, slot } } });
}
