// Validates drizzle/: migration numbers are contiguous from 0000.
import { readdirSync } from "node:fs";

export function checkSequence(files) {
	const nums = files.filter((f) => /^\d{4}_.*\.sql$/.test(f)).map((f) => Number(f.slice(0, 4))).sort((a, b) => a - b);
	const problems = [];
	nums.forEach((n, i) => {
		if (n !== i) problems.push(`expected ${String(i).padStart(4, "0")}, found ${String(n).padStart(4, "0")}`);
	});
	return problems;
}

if (import.meta.url === `file://${process.argv[1]}`) {
	const problems = checkSequence(readdirSync("drizzle"));
	if (problems.length) {
		console.error(problems.join("\n"));
		process.exit(1);
	}
	console.log("migration sequence ok");
}
