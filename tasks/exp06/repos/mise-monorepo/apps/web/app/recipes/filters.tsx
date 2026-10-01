"use client";

// Filter bar: every control writes a search param the page reads.
export function RecipeFilters() {
	return (
		<form method="get">
			<input name="q" placeholder="Search recipes" />
			<select name="cuisine">
				<option value="">Any cuisine</option>
				<option>Italian</option>
				<option>Mexican</option>
				<option>Japanese</option>
			</select>
			<select name="diet">
				<option value="">Any diet</option>
				<option value="vegetarian">Vegetarian</option>
				<option value="vegan">Vegan</option>
				<option value="gluten-free">Gluten-free</option>
			</select>
			<select name="time">
				<option value="">Any time</option>
				<option value="20">Under 20 min</option>
				<option value="45">Under 45 min</option>
			</select>
			<button type="submit">Filter</button>
		</form>
	);
}
