import { prisma } from "@mise/core/db";
import { stripe } from "@/lib/stripe";

export async function POST(req: Request) {
	const sig = req.headers.get("stripe-signature") ?? "";
	const event = stripe.webhooks.constructEvent(await req.text(), sig, process.env.STRIPE_WEBHOOK_SECRET ?? "");
	if (event.type === "checkout.session.completed") {
		const s = event.data.object;
		const sub = await stripe.subscriptions.retrieve(s.subscription as string);
		await prisma.subscription.upsert({
			where: { userId: s.client_reference_id! },
			create: {
				userId: s.client_reference_id!,
				stripeCustomerId: s.customer as string,
				stripeSubscriptionId: sub.id,
				status: sub.status,
				currentPeriodEnd: new Date(sub.items.data[0].current_period_end * 1000),
			},
			update: { status: sub.status, currentPeriodEnd: new Date(sub.items.data[0].current_period_end * 1000) },
		});
	}
	if (event.type === "customer.subscription.deleted") {
		const sub = event.data.object;
		await prisma.subscription.update({ where: { stripeSubscriptionId: sub.id }, data: { status: "canceled" } });
	}
	return new Response("ok");
}
