export type CartLine = { name: string; quantity: number; unit: string };

export interface GroceryAdapter {
	id: "instacart" | "kroger";
	label: string;
	enabled(): boolean;
	/** Either a URL to open, or a created cart. */
	send(lines: CartLine[]): Promise<{ kind: "link"; url: string } | { kind: "cart"; cartId: string }>;
}
