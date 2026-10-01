import { pgTable, text } from "drizzle-orm/pg-core";

export const role = pgTable("role", {
	id: text("id").primaryKey(),
	title: text("title").notNull(),
});
