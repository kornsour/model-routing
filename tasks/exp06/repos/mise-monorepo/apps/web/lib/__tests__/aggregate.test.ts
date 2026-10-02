import { describe, expect, it } from "vitest";
import { buildGroceryList } from "../grocery/aggregate";

describe("buildGroceryList", () => {
	it("sums the same ingredient across recipes in base units", () => {
		const items = buildGroceryList(
			[{ recipeId: "a", servings: 2 }, { recipeId: "b", servings: 4 }],
			[
				{ id: "a", ingredients: [{ name: "Flour", quantity: 0.5, unit: "kg" }] },
				{ id: "b", ingredients: [{ name: "flour", quantity: 100, unit: "g" }] },
			],
		);
		expect(items).toEqual([{ name: "flour", unit: "g", quantity: 700 }]);
	});
});
