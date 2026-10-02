// Builds the week's grocery list from the planner: every assigned recipe's
// ingredients, scaled by servings, summed per ingredient after converting to
// a base unit (g, ml, or count).

type Assignment = { recipeId: string; servings: number };
type Ingredient = { name: string; quantity: number; unit: string };
type RecipeWithIngredients = { id: string; ingredients: Ingredient[] };

const TO_BASE: Record<string, [string, number]> = {
	g: ["g", 1],
	kg: ["g", 1000],
	ml: ["ml", 1],
	l: ["ml", 1000],
	tsp: ["ml", 5],
	tbsp: ["ml", 15],
	cup: ["ml", 240],
	pc: ["pc", 1],
};

export function buildGroceryList(assignments: Assignment[], recipes: RecipeWithIngredients[]) {
	const byId = new Map(recipes.map((r) => [r.id, r]));
	const totals = new Map<string, { name: string; unit: string; quantity: number }>();
	for (const a of assignments) {
		const recipe = byId.get(a.recipeId);
		if (!recipe) continue;
		for (const ing of recipe.ingredients) {
			const [unit, factor] = TO_BASE[ing.unit] ?? [ing.unit, 1];
			const key = `${ing.name.toLowerCase()}|${unit}`;
			const scaled = (ing.quantity * factor * a.servings) / 2; // recipes are written for 2
			const prev = totals.get(key);
			totals.set(key, { name: ing.name, unit, quantity: (prev?.quantity ?? 0) + scaled });
		}
	}
	return [...totals.values()].sort((x, y) => x.name.localeCompare(y.name));
}
