"use client";

export function ListActions({ items }: { items: { name: string; quantity: number; unit: string }[] }) {
	const text = items.map((i) => `${i.quantity} ${i.unit} ${i.name}`).join("\n");
	return (
		<div>
			<button onClick={() => navigator.clipboard.writeText(text)}>Copy list</button>
			<button onClick={() => window.print()}>Print</button>
		</div>
	);
}
