import { Queue } from "./pages/Queue";
import { Ticket } from "./pages/Ticket";
import { Approvals } from "./pages/Approvals";

export function App({ route }: { route: string }) {
	if (route.startsWith("/tickets/")) return <Ticket id={route.split("/")[2]} />;
	if (route === "/approvals") return <Approvals />;
	return <Queue />;
}
