import type { CartLine, GroceryAdapter } from "./types";

// No partner API access: open Instacart's search for the first item so the
// user can shop from there. One search per line is too many tabs.
export const instacart: GroceryAdapter = {
	id: "instacart",
	label: "Instacart",
	enabled: () => true,
	async send(lines: CartLine[]) {
		const q = encodeURIComponent(lines.map((l) => l.name).slice(0, 5).join(" "));
		return { kind: "link", url: `https://www.instacart.com/store/s?k=${q}` };
	},
};
