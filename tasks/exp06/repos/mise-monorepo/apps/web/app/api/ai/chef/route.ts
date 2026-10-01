import OpenAI from "openai";
import { requireUser } from "@/lib/auth";

const openai = new OpenAI();

export async function POST(req: Request) {
	await requireUser();
	const { prompt } = await req.json();
	const completion = await openai.chat.completions.create({
		model: "gpt-4.1-mini",
		messages: [
			{ role: "system", content: "You are a helpful home chef." },
			{ role: "user", content: String(prompt).slice(0, 2000) },
		],
	});
	return Response.json({ answer: completion.choices[0].message.content });
}
