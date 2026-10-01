# mise: portfolio claims vs code

1. **Recipe discovery — PARTIAL.** `apps/web/app/recipes/page.tsx` passes q, cuisine, diet and time to `searchRecipes` (`apps/web/lib/recipes/query.ts`), which wires q, cuisine and `totalMinutes <= time` into the Prisma query but ignores `diet` (a TODO). The diet filter is decorative.
2. **Weekly planner — IMPLEMENTED.** Week grid (`apps/web/app/planner/week-grid.tsx`) calls server actions in `apps/web/app/actions/planner.ts` that upsert `MealPlan` / `MealAssignment` rows; `/plans` lists saved weeks.
3. **Auto-generated grocery lists — IMPLEMENTED.** `apps/web/lib/grocery/aggregate.ts` derives the list from the week's assignments, scales by servings and sums per ingredient in base units (g, ml, pc). Copy and print exist; nothing is entered by hand.
4. **Grocery-store integration — PARTIAL (no real provider integration).** Instacart is a deep link to its search URL (b); the Kroger adapter is a mock that returns `mock-<n>-<ts>` cart ids with no HTTP call (c), behind `GROCERY_PROVIDER_KROGER`, unset in `.env.example` (d). The UI shows "Kroger (coming soon)".
5. **Subscription billing — PARTIAL.** Checkout session creation, a webhook that upserts `Subscription`, and `isPro()` exist and work in test or live mode depending on keys. But the "Pro Required" AI Chef Assistant is gated only by the page: `apps/web/app/api/ai/chef/route.ts` checks the session, not `isPro`, so any signed-in user can call it. PDF export does enforce Pro server-side.

```json
{"claims": {"recipe_discovery": "PARTIAL", "weekly_planner": "IMPLEMENTED", "grocery_lists": "IMPLEMENTED", "store_integration": "PARTIAL", "subscription_billing": "PARTIAL"},
 "decorative_recipe_filters": ["diet"], "store_real_provider_api": false, "ai_chef_entitlement_enforced_server_side": false}
```
