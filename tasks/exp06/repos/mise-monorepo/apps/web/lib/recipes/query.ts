import { prisma } from "@mise/core/db";

export type RecipeSearch = { q?: string; cuisine?: string; diet?: string; maxMinutes?: number };

export async function searchRecipes(search: RecipeSearch) {
	const where: Record<string, unknown> = {};
	if (search.q) where.title = { contains: search.q, mode: "insensitive" };
	if (search.cuisine) where.cuisine = search.cuisine;
	if (search.maxMinutes) where.totalMinutes = { lte: search.maxMinutes };
	// TODO(diets): filter on Recipe.diets once the seed data has diet tags.
	return prisma.recipe.findMany({ where, orderBy: { title: "asc" }, take: 50 });
}
