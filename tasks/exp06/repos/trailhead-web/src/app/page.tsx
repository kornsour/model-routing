import Link from "next/link";
import { FEATURE_CARDS } from "@/content/marketing";

export default function HomePage() {
	return (
		<main className="mx-auto max-w-4xl px-6 py-16">
			<section className="space-y-6">
				<p className="text-sm font-medium uppercase tracking-wide text-muted">
					Pathwise
				</p>
				{/* The hero. Keep it to one line on a laptop screen. */}
				<h1 className="text-4xl font-semibold tracking-tight">
					Run your job search like a portfolio, not a lottery.
				</h1>
				<p className="max-w-2xl text-lg text-muted">
					Pathwise sources roles, scores fit, tailors your materials, and drafts
					outreach — autonomously where you want it, held for review where it
					matters. A persistent context library keeps every agent consistent, and
					nothing is sent, submitted, or saved without passing your desk.
				</p>
				<div className="flex gap-3">
					<Link href="/sign-in" className="btn btn-primary">
						Sign in
					</Link>
					<Link href="/docs" className="btn">
						How it works
					</Link>
				</div>
			</section>
			<section className="mt-16 grid gap-6 sm:grid-cols-2">
				{FEATURE_CARDS.map((card) => (
					<article key={card.title} className="rounded-lg border p-5">
						<h2 className="font-medium">{card.title}</h2>
						<p className="mt-2 text-sm text-muted">{card.body}</p>
					</article>
				))}
			</section>
		</main>
	);
}
