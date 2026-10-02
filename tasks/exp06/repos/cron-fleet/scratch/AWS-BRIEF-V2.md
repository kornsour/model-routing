# AWS move, brief v2 (context only)

The Copperline apps are moving off Vercel onto AWS over the next month. Other
agents are writing the deploy scripts and the IAM roles in other repos. The
cron routes keep the same HTTP contract after the move: a scheduler calls them
with `Authorization: Bearer <CRON_SECRET>`, so whatever authorization the
routes enforce today is what they will enforce on AWS.
