import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { PRO_PRICE, stripe } from "@/lib/stripe";

export async function POST() {
	const user = await requireUser();
	const session = await stripe.checkout.sessions.create({
		mode: "subscription",
		line_items: [{ price: PRO_PRICE, quantity: 1 }],
		customer_email: user.email,
		client_reference_id: user.id,
		success_url: `${process.env.NEXTAUTH_URL}/account?upgraded=1`,
		cancel_url: `${process.env.NEXTAUTH_URL}/pricing`,
	});
	return NextResponse.redirect(session.url!, 303);
}
