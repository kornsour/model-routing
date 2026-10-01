// Drafts only. There is no send path from this page by design: an outbound
// message is a requestAction("send_email") that the operator approves, and it
// still goes nowhere while OUTBOUND_SENDING is off.
export default function MessagesPage() {
	return <main>Drafts</main>;
}
