import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
	title: "Pathwise",
	description: "Run your job search like a portfolio, not a lottery.",
	openGraph: {
		title: "Pathwise",
		description: "Run your job search like a portfolio, not a lottery.",
	},
};

export default function RootLayout({ children }: { children: ReactNode }) {
	return (
		<html lang="en">
			<body>{children}</body>
		</html>
	);
}
