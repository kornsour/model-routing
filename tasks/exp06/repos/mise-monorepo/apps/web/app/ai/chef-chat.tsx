"use client";

import { useState } from "react";

export function ChefChat() {
	const [answer, setAnswer] = useState("");
	async function ask(form: FormData) {
		const res = await fetch("/api/ai/chef", { method: "POST", body: JSON.stringify({ prompt: form.get("prompt") }) });
		setAnswer((await res.json()).answer);
	}
	return (
		<form action={ask}>
			<textarea name="prompt" />
			<button>Ask</button>
			<p>{answer}</p>
		</form>
	);
}
