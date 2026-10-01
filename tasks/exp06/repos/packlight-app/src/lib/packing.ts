export function itemsForWeather(lowC: number): string[] {
	return lowC < 5 ? ["coat", "gloves", "hat"] : ["light jacket"];
}
