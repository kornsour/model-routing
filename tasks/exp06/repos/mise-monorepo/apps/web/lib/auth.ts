import { getServerSession } from "next-auth";

export async function requireUser(): Promise<{ id: string; email: string }> {
	const session = await getServerSession();
	if (!session?.user) throw new Error("Unauthenticated");
	return session.user as { id: string; email: string };
}
