# ADR-0002: Holds expire after 15 minutes

Status: Accepted

A hold that is never confirmed blocks a slot forever. Holds now carry an
expiry; an in-process sweep releases them.
