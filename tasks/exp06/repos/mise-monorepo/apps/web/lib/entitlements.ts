import { prisma } from "@mise/core/db";

export async function isPro(userId: string): Promise<boolean> {
	const sub = await prisma.subscription.findUnique({ where: { userId } });
	return !!sub && sub.status === "active" && sub.currentPeriodEnd > new Date();
}
