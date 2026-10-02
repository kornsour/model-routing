# Runner ↔ dashboard event protocol

The real runner streams `orchestra.model.Event`s to the dashboard's event
log over a message bus. Delivery is **at-least-once**: after a reconnect the
runner resends every event the bus did not acknowledge, and some of those
had in fact been delivered.

Properties the consumers may rely on:

- An event is identified by `(job, kind, attempt)`. No two distinct events
  share an identity: a job's attempt `n` starts once, ends once.
- A resent copy is otherwise identical except that its `time` and `detail`
  may differ: the runner stamps the resend time, and for `retry` events it
  recomputes the retry time from the resend time.
- **The first copy received is authoritative.** Later copies carry no new
  information and must be ignored, wherever they appear in the log.
- Events of one job arrive in order; events of different jobs may
  interleave arbitrarily.
