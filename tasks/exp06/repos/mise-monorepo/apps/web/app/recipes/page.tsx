import { searchRecipes } from "@/lib/recipes/query";
import { RecipeFilters } from "./filters";

export default async function RecipesPage({ searchParams }: { searchParams: Record<string, string | undefined> }) {
	const recipes = await searchRecipes({
		q: searchParams.q,
		cuisine: searchParams.cuisine,
		diet: searchParams.diet,
		maxMinutes: searchParams.time ? Number(searchParams.time) : undefined,
	});
	return (
		<main>
			<h1>Discover recipes</h1>
			<RecipeFilters />
			<ul>
				{recipes.map((r) => (
					<li key={r.id}>
						{r.title} · {r.cuisine} · {r.totalMinutes} min
					</li>
				))}
			</ul>
		</main>
	);
}
