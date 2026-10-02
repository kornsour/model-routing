import assert from "node:assert/strict";
import { test } from "node:test";
import { outboundSendingEnabled, requestAction } from "./autonomy.ts";

test("outbound sending is off by default", () => {
	assert.equal(outboundSendingEnabled({}), false);
	assert.equal(requestAction("send_email", {}).status, "approved_not_sent");
});
