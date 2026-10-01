// The outbound kill switch. Off unless the operator sets OUTBOUND_SENDING=on.
export function outboundSendingEnabled(env: Record<string, string | undefined>): boolean {
	return env.OUTBOUND_SENDING === "on";
}

export type ActionKind = "send_email" | "submit_application" | "configure_board";

// Anything that leaves the app is held for review; with sending off, an
// approved outbound action is recorded but never delivered.
export function requestAction(
	kind: ActionKind,
	env: Record<string, string | undefined>,
): { status: "held" | "approved_not_sent" } {
	if (kind === "configure_board") return { status: "held" };
	return outboundSendingEnabled(env) ? { status: "held" } : { status: "approved_not_sent" };
}
