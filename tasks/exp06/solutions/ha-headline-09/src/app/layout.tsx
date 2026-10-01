import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
	title: "Pathwise",
	description: "Automate the busywork of building a career.",
	openGraph: {
		title: "Pathwise",
		description: "Automate the busywork of building a career.",
	},
};

export default function RootLayout({ children }: { children: ReactNode }) {
	return (
		<html lang="en">
			<body>{children}</body>
		</html>
	);
}
