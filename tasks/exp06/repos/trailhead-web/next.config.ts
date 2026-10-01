import type { NextConfig } from "next";

const config: NextConfig = {
	// Load-bearing: the repo root holds two workspaces.
	turbopack: { root: import.meta.dirname },
};

export default config;
