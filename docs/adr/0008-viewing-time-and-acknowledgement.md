# ADR 0008: Viewing time and acknowledgement evidence

- Status: Accepted
- Date: 2026-07-24

## Decision

Record foreground viewing time separately from the user’s compliance action.
Client-side activity and page visibility produce a proposed active duration when
the reader closes a message. The server caps that duration to the wall-clock
viewing session, credits it once, and accumulates it across sessions.

Opening a message is not acknowledgement. **Read** records that the content was
read but leaves a mandatory item in the Mandatory Messages list. **Read & Clear**
is the explicit compliance acknowledgement and moves it to Other Messages. The
interface and reporting data use those terms consistently.

Message opens, reads, clearances, prints, email-to-self and feedback actions create
append-only structured access events plus the shared audit event. The logout
confirmation reads the server session’s deduplicated access list.

Protected PDFs are streamed only through an authorised same-origin endpoint with
private no-store caching. Email-to-self for an Instruction contains an
authenticated link rather than attaching or exposing the protected PDF.

## Consequences

Viewing duration is useful supporting evidence but cannot be represented as proof
that content was understood. Idle detection is deliberately conservative and the
server does not trust unbounded client duration. Replaying a closed view session
cannot add time or acknowledgement evidence.

Users can print through a dedicated print view and email a message to their
registered address. Feedback is queued to the originator and authorised
administrators. These delivery requests reuse the recoverable notification job
pipeline.
