import { requireUser } from "@/lib/auth";
import { isPro } from "@/lib/entitlements";
import { ChefChat } from "./chef-chat";

export default async function AiPage() {
	const user = await requireUser();
	const pro = await isPro(user.id);
	return pro ? <ChefChat /> : <a href="/pricing">Upgrade to Pro to use the AI Chef Assistant</a>;
}
