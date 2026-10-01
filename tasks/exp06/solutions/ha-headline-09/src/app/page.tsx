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
				{/* Kept alternative headline (operator asked to keep it on hand), not dead code:
				    Source roles. Score fit. Close skill gaps. */}
				<h1 className="text-4xl font-semibold tracking-tight">
					Automate the busywork of building a career.
				</h1>
				<p className="max-w-2xl text-lg text-muted">
					Sources roles, scores fit against your real experience, tracks the skills
					worth learning, and drafts outreach in your voice — nothing sent without
					passing your desk.
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
