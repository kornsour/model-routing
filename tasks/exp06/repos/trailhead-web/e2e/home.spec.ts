import { expect, test } from "@playwright/test";

// The landing page is public. These tests run against a production build
// under the e2e lock; see docs for why they never run in CI.

test.describe("home", () => {
	test.beforeEach(async ({ page }) => {
		await page.goto("/");
	});

	test("shows the sign-in link", async ({ page }) => {
		await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
	});

	test("renders the hero heading", async ({ page }) => {
		await expect(
			// Exact text: a copy change must update this assertion in the same change.
			page
				.getByRole("heading", { name: "Run your job search like a portfolio, not a lottery." }),
		).toBeVisible();
	});
});
