import { instacart } from "./instacart";
import { kroger } from "./kroger";

export const ADAPTERS = [instacart, kroger];

export function availableAdapters() {
	return ADAPTERS.filter((a) => a.enabled());
}
