"use server";

import { requireUser } from "@/lib/auth";
import { isPro } from "@/lib/entitlements";

// PDF export of a week's plan is a Pro feature.
export async function exportPlanPdf(planId: string) {
	const user = await requireUser();
	if (!(await isPro(user.id))) throw new Error("Pro required");
	return { url: `/exports/${planId}.pdf` };
}
