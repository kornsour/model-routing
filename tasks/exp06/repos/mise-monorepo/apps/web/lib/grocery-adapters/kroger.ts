import type { CartLine, GroceryAdapter } from "./types";

// Kroger Cart API adapter. Behind GROCERY_PROVIDER_KROGER until we have
// production OAuth credentials; until then send() returns a placeholder cart
// so the UI flow can be built and demoed.
export const kroger: GroceryAdapter = {
	id: "kroger",
	label: "Kroger",
	enabled: () => process.env.GROCERY_PROVIDER_KROGER === "1",
	async send(lines: CartLine[]) {
		// TODO: OAuth (authorization code) + PUT https://api.kroger.com/v1/cart/add
		const cartId = `mock-${lines.length}-${Date.now()}`;
		return { kind: "cart", cartId };
	},
};
