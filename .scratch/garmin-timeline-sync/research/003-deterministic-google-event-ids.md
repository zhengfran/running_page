# Deterministic Google Calendar Event IDs for the Garmin Sync Job

Research date: 2026-08-26

## Verdict

1. **Format constraints on caller-supplied `id`:** Allowed characters are `a-v` (lowercase only) and `0-9` — the "base32hex" alphabet, RFC2938 §3.1.2. Length must be **5–1024 characters**. Uniqueness is **per calendar**, and it includes cancelled/deleted "tombstone" events, not just currently-visible ones (see Q5). No uppercase, no `-`, no `_`, no other punctuation is permitted.

2. **Conforming encoding:** Drop separators entirely; use a single leading type-tag letter drawn from `a-v` concatenated directly with digits. Recommended scheme:
   - Activity: `"a" + <decimal activity id>` → `a12345678901`
   - Sleep: `"b" + <date compact, no dashes>` → `b20260825`
   A prefix like `garmin-activity-` is non-conforming twice over: `-` is not in the allowed set, and `g`, `r`, `m`, `t`, `y` are all outside `a-v`... actually `g,r,m,t,y` — only `y` and letters after `v` (`w,x,y,z`) are the actual violators, but the point stands generally for arbitrary English words. Never assume a human-readable prefix is safe; check every character against `a-v0-9`.

3. **Existing-id behavior on `events.insert`:** Documented, explicit **HTTP 409, reason `duplicate`**, message *"The requested identifier already exists."* This is not a silent no-op and not an overwrite. The official error-handling guide's prescribed fix is: *"Generate new ID or use the `events.update` method."* Correct pattern for this job: **insert; on 409, `events.get` then `events.patch`** (patch, not update — see Q4) to write the new field values. `events.import` is a materially different, less-suited tool: it keys off `iCalUID` (required for import, not the deterministic `id` this design wants), the Calendar API discovery document shows `events.import` has **no `sendUpdates` parameter at all**, and the docs do not state what happens on a repeated `iCalUID`. It's not the documented mechanism for this job's id-based idempotency.

4. **Clobbering / notifications on update:** `events.update` is a full PUT — the docs state it plainly: *"This method does not support patch semantics and always updates the entire event resource"* and recommend a get-then-update with etags. Any field the job's PUT body omits (colorId, per-event reminder overrides, a user's manual description edit) is at risk of being reset/cleared, silently clobbering the user's edit. **`events.patch` avoids this** — its docs state *"Fields that you don't specify in the request remain unchanged."* Use patch for the repeated sleep-record re-touch. On notifications: `sendUpdates=none` is available on both insert/update/patch and suppresses guest notifications, but the docs carry an explicit caveat on every one of these methods: *"Note that some emails might still be sent even if you set the value to false."* The docs do not enumerate which circumstances still trigger mail. `events.import`, by contrast, exposes no `sendUpdates` parameter at all in the API surface, per the discovery document — structurally it cannot send guest notifications, though this is not what the id design should be built on (see Q3). The docs do not state anything about the update repositioning the event in the UI; that risk is not documented either way (see the Q4 detail section for reasoning).

5. **Deleted-id reuse:** Deletion does **not** free the ID. The event flips to `status: "cancelled"` and persists as a tombstone that continues to occupy the id space — `events.get` "always returns" cancelled events for the organizer, with full detail retained specifically *"so that they can be restored (undeleted)."* A subsequent `events.insert` with the same id gets the 409 `duplicate` from Q3, confirmed in practice by a community bug report. The tombstone is not stated to be permanent — the docs say cancelled events *"will eventually disappear, so do not rely on them being available indefinitely"* — and Google's consumer Calendar help states the visible Trash retains deleted events for 30 days before permanent purge, though that specific number is documented on the consumer help site, not the API reference, so its exact applicability to API-level id reuse is not officially guaranteed. **Practical consequence for the design:** a user-deleted record does not silently and permanently block re-sync, but it also will not "just reappear" from a plain insert — the job must explicitly detect the 409, `get` the tombstone, and decide whether to revive it (patch `status` back to `"confirmed"`) or leave it deleted. The API does not make this choice for you either way.

---

## Q1 — Format constraints on the `id` field

Primary source (Event resource reference, and identical text in the discovery document served live from `googleapis.com`):

> "Opaque identifier of the event. When creating new single or recurring events, you can specify their IDs. Provided IDs must follow these rules:
> - characters allowed in the ID are those used in base32hex encoding, i.e. lowercase letters a-v and digits 0-9, see section 3.1.2 in RFC2938
> - the length of the ID must be between 5 and 1024 characters
> - the ID must be unique per calendar
>
> Due to the globally distributed nature of the system, we cannot guarantee that ID collisions will be detected at event creation time. To minimize the risk of collisions we recommend using an established UUID algorithm such as one described in RFC4122.
> If you do not specify an ID, it will be automatically generated by the server.
> Note that the icalUID and the id are not identical and only one of them should be supplied at event creation time."

Source: https://developers.google.com/workspace/calendar/api/v3/reference/events (Event resource, `id` field), corroborated verbatim in the live Calendar v3 Discovery Document at `https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest` (schemas.Event.properties.id).

Same wording is repeated on the request-body id parameter of the insert method: https://developers.google.com/workspace/calendar/api/v3/reference/events/insert

Key points:
- The charset check is purely a **character-class** constraint ("characters allowed... are those used in base32hex encoding"), not a requirement that the string decode as a valid base32hex-encoded binary payload. The docs do not state that the id must round-trip through an actual base32hex decoder — it only restricts the *alphabet*.
- Case matters: only **lowercase** `a`–`v` is allowed; uppercase is not mentioned as accepted anywhere in the reference.
- "Unique per calendar" is stated plainly, but the docs do not explicitly define, in this same sentence, whether that uniqueness scope includes cancelled/deleted events — that is established by the `status` field text and 409 behavior discussed under Q3/Q5, not by the `id` field text itself.
- The docs explicitly warn that ID-collision detection is not guaranteed at creation time ("due to the globally distributed nature of the system"), which softens any assumption of a strongly-consistent, always-detected 409 — see the caveat under Q3.

## Q2 — Encoding a Garmin activity id / sleep date into a conforming id

There is no dedicated Google doc for "how to encode external ids" beyond the character/length/uniqueness rules in Q1, plus the guidance in the official "Create events" guide:

> "When creating an event, you can choose to generate your own event ID that conforms to format requirements... This lets you keep entities in your local database in sync with events in Calendar. It also prevents duplicate event creation if the operation fails at some point after it is successfully executed in the Calendar backend."

Source: https://developers.google.com/workspace/calendar/api/guides/create-events

This guide does not give a worked example of encoding an external numeric id into the base32hex charset — that part is left to the implementer, hence the trap noted in the task brief.

Working through the constraint:
- Digits `0`–`9` are directly in the allowed set, so a raw decimal Garmin activity id (e.g. `12345678901`) is, character-for-character, already conforming and within the 5–1024 length window.
- A date key like `2026-08-25` is **not** conforming as written — the `-` characters are outside `a-v0-9`. Stripping the dashes (`20260825`) makes it conforming and unambiguous (fixed-width, no separator needed).
- The stated trap — a natural prefix like `garmin-activity-` — fails on two independent grounds: (a) the `-` character itself, and (b) any letter outside `a`–`v` (i.e. `w`, `x`, `y`, `z` are never usable; note that most of `g`,`r`,`m`,`t` individually *are* inside `a-v`, so the failure isn't "all letters," it's "any letter past v," which is easy to miss when picking a human-readable word).
- **Recommended scheme:** a single leading type-tag character chosen from `a`–`v`, followed immediately by the digits, no separators:
  - Activity `12345678901` → `a12345678901` (13 chars)
  - Sleep date `2026-08-25` → `b20260825` (9 chars)
  Both are well inside the 5–1024 length bound, both are trivially reversible/greppable for debugging, and the leading tag prevents any possible collision between an activity id and a sleep date that happen to share the same digit string.
- If a richer namespace is wanted later, hex-encoding an arbitrary byte string (e.g. `hashlib.sha1(...).hexdigest()`) also conforms, since hex digits `0-9a-f` are a subset of `a-v0-9` — but plain digits/tag-letter is simpler and sufficient for this job's two known record types.

**Confidence caveat:** the claim that the charset is purely a character-class filter (not a semantic base32hex-decode validation) is not tested against the live API in this research pass — it rests on the literal wording of the doc ("characters allowed in the ID are those used in..."), which is the natural reading, and is consistent with widely-reported practitioner usage of arbitrary digit/letter strings as ids. No official worked example was found confirming this beyond the wording itself.

## Q3 — `events.insert` with an id that already exists; correct create-or-update pattern

**409 Conflict, explicitly documented**, from Google's own error-handling guide:

> "409: The requested identifier already exists — Reason: `duplicate` — Message: 'The requested identifier already exists.' — Handling: Generate new ID or use the `events.update` method."

Source: https://developers.google.com/workspace/calendar/api/guides/errors

This is not a silent no-op and not a silent overwrite — it is a hard error surfaced to the caller, and the docs' own suggested remediation is exactly the fallback-to-update pattern this design needs.

**Recommended call pattern**, built directly from documented behavior:
1. `events.insert` with the deterministic id.
2. On success → done, this is a first-time write.
3. On HTTP 409 / reason `duplicate` → the id is already occupied (which, per Q5, may be either a live event or a cancelled tombstone). Call `events.get` for that id (organizer's `get` is documented to "always return" the event, including cancelled ones, per the `status` field text) to inspect current state, then `events.patch` (not `events.update` — see Q4) with the new field values (and, if reviving a tombstone, explicitly set `status: "confirmed"`).

**`events.update` requiring pre-existence:** the reference page does not explicitly spell out "the event must already exist," but this is implied by its being a full-resource PUT against `.../events/{eventId}`, and is corroborated by widely-reported 404/`notFound` behavior when the target id doesn't exist (Google's documented general error table lists `404 notFound` as a standard error reason — https://developers.google.com/workspace/calendar/api/guides/errors — though that page does not call out events.update by name for this specific case). Treat "update requires existence, else 404" as consistent with documented REST semantics but not verbatim-quoted for the update method specifically.

**`events.import` vs `events.insert` on ids:** these are materially different mechanisms, not two spellings of the same idempotency guarantee:
- `import`'s documented purpose is narrower: *"add a private copy of an existing event to a calendar"* — for migrating events between calendaring systems — and it **requires `iCalUID`** (per the discovery document's `annotations.required: ["calendar.events.import"]` on the `iCalUID` field), not the caller's own `id`. Source: https://developers.google.com/workspace/calendar/api/v3/reference/events/import and the live discovery doc.
- The docs state *"only events with an `eventType` of `default` may be imported"* and that importing a non-default event silently changes its type and drops event-type-specific properties.
- The docs do **not** state what happens if you `import` twice with the same `iCalUID` (no documented 409/duplicate-iCalUID behavior was found for import specifically).
- Structurally, `events.import` exposes **no `sendUpdates` parameter at all** — confirmed directly from the live Calendar v3 Discovery Document (`resources.events.methods.import.parameters` has no `sendUpdates` key, unlike insert/update/patch/delete, which all do). This means import cannot be told to notify guests, and by the same token cannot accidentally not-notify in some edge case the way insert/update's documented "some emails might still be sent" caveat implies.
- Given the design's actual idempotency key is a **caller-computed `id`**, not an RFC5545 `iCalUID`, `events.import` is not the documented tool for this job — `events.insert` (id-first) with 409-then-patch is.

## Q4 — Clobbering, position/colour/reminders, and notifications on update

**Full-replace semantics, documented explicitly:**

> "This method does not support patch semantics and always updates the entire event resource."

Source: https://developers.google.com/workspace/calendar/api/v3/reference/events/update

The same page's guidance for doing a safe partial change is: *"To do a partial update, perform a `get` followed by an `update` using etags to ensure atomicity."* This is Google's own acknowledgement that a naive PUT with a partial body will lose data — i.e. **yes, a plain `events.update` call that omits a field the user manually set (colour, per-event reminder override, a note added to the description) can clobber it**, because any field absent from the PUT body is not guaranteed to be preserved.

`events.patch`, by contrast, is explicitly the safe tool for this:

> "The field values you specify replace the existing values. Fields that you don't specify in the request remain unchanged."

Source: https://developers.google.com/workspace/calendar/api/v3/reference/events/patch

**Recommendation for this job:** use `events.patch`, sending only the fields the job owns (times, description/body content it manages), so it never touches `colorId` or `reminders` unless it explicitly means to. This directly serves the stated goal of "silent, invisible updates... re-processing the same [sleep] record several days running" without disturbing anything the user touched by hand.

**Reminders specifically:** the docs note reminders are inherited from calendar defaults via `useDefault`, and overriding requires `useDefault: false` plus a populated `overrides` array (source: https://developers.google.com/workspace/calendar/api/concepts/reminders). The docs do not explicitly state what happens if the `reminders` field is omitted entirely from a `patch` body — but per patch's own stated contract ("fields you don't specify... remain unchanged"), omitting `reminders` from a patch should leave whatever reminder configuration currently exists untouched. This inference follows directly from the general patch contract but is not spelled out with a reminders-specific example in the docs, so treat it as medium confidence.

**Notifications:** `sendUpdates` (insert/update/patch/delete) accepts `all` / `externalOnly` / `none`, and every one of the current reference pages that expose it carries the same caveat:

> "Note that some emails might still be sent even if you set the value to false [i.e. sendUpdates=none]."

Sources: https://developers.google.com/workspace/calendar/api/v3/reference/events/insert, https://developers.google.com/workspace/calendar/api/v3/reference/events/update, https://developers.google.com/workspace/calendar/api/v3/reference/events/patch

**What the docs do not state:** which specific circumstances still cause mail with `sendUpdates=none` (e.g. whether the calendar owner's own account can receive a notification distinct from "guest" notifications is not addressed — the parameter description everywhere is phrased in terms of "guests"/"attendees," and this job's calendar presumably has none). Also not addressed anywhere: whether an update (regardless of `sendUpdates`) changes the event's position/order in the calendar UI, or resets a colour the job's PUT/PATCH body didn't touch (partially answered above for PATCH: no, because unspecified fields are left alone) or triggers a client-side push/desktop notification (as opposed to email) on the owner's devices. For UI position: Calendar's rendering is driven by `start`/`end`, not last-modified time, and neither `events.update` nor `events.patch` reference pages mention any UI reordering side effect — this is treated as a reasonable inference (not a documented guarantee) since the design does not appear to change start/end times on the repeated sleep-record touches. Flagged as "docs are silent" rather than a confirmed guarantee.

Community corroboration for the sendUpdates=none caveat's practical bite: there is an unresolved Google Issue Tracker report titled "Calendar API ignoring sendUpdates=none parameter" (https://issuetracker.google.com/issues/410721178) surfaced in search results; its content requires Google sign-in and could not be read during this research pass, so it is cited only as a pointer to further community-reported friction around this exact parameter, not as a verified fact — treat with low confidence until read directly.

## Q5 — What happens to a deterministic id after the event is deleted

**Deletion is a soft-delete / tombstone, not a hard removal**, per the `status` field's own documentation on the Event resource:

> "cancelled — The event is cancelled (deleted). The list method returns cancelled events only on incremental sync (when syncToken or updatedMin are specified) or if the showDeleted flag is set to true. The get method always returns them... All other cancelled events represent deleted events. Clients should remove their locally synced copies. Such cancelled events will eventually disappear, so do not rely on them being available indefinitely. Deleted events are only guaranteed to have the id field populated. On the organizer's calendar, cancelled events continue to expose event details (summary, location, etc.) so that they can be restored (undeleted)."

Source: https://developers.google.com/workspace/calendar/api/v3/reference/events (Event resource, `status` field), corroborated verbatim in the live Discovery Document.

This directly establishes:
- Deletion does **not** immediately free the id. The event persists at that id with `status: "cancelled"`.
- `events.get` "always returns" cancelled events for the organizer, with details retained specifically to support restoration — i.e. there is an official notion of "restore (undelete)," though the docs do not give a worked API example of *how* (no explicit "call patch with `status: confirmed`" snippet was found). This mechanism (flip `status` back to `confirmed` via `patch`) is the logical implementation of "restore" given the resource model, and matches an unverified/self-discovered community report — a June 2014 Google Calendar API mailing-list post (https://groups.google.com/g/google-calendar-api/c/-LjQNogXe3U, posted 2014-06-16) in which a developer, finding no official answer in the thread, proposed exactly this (`get` shows status cancelled → set status back to confirmed and call patch). No Google staff response confirmed this in that thread. **This specific "how to revive" mechanism should be treated as community-sourced (2014-06-16, unconfirmed by Google staff), not an official documented procedure**, even though the general "cancelled events can be restored" concept is official.
- **Re-inserting with the same id after deletion produces the 409 `duplicate` error from Q3, not a fresh insert.** This is the direct, load-bearing consequence for the design and is corroborated by a community GitHub issue (opened 2020-03-20, https://github.com/googleapis/google-api-python-client/issues/846) in which a user reports that after deleting Calendar events, subsequent inserts with the same id fail with "The requested identifier already exists," because the deleted event persists as a tombstone. The issue was labeled "external" (i.e. attributed to Calendar's own behavior, not a client-library bug), with no further resolution documented. **Community-sourced, dated 2020-03-20.**
- The tombstone is documented as **not permanent**: "will eventually disappear, so do not rely on them being available indefinitely" (official, from the `status` field text above) — but the API reference does not state a concrete retention period.
- Google's consumer-facing Calendar Help does state a concrete number for the visible Trash: *"When you delete an event... it stays in that calendar's trash for 30 days"* before permanent deletion (source: https://support.google.com/calendar/answer/37113). This is an official Google page, but it is the **consumer product help center, not the API reference** — the task brief's instruction to treat non-API-reference sources cautiously applies here: this 30-day figure is stated with confidence for the UI Trash feature, but the docs do not explicitly confirm that the same 30-day clock is what governs id-reuse eligibility at the API level, even though it is presumably the same underlying storage (both are driven by the same `status: cancelled` tombstone mechanism). Treat "~30 days, then the id is likely free again" as a reasonable but not API-doc-confirmed inference.

**Net effect on the design:** a Garmin record whose Google event the user manually deletes will not be silently, permanently un-syncable — the tombstone eventually expires (informally, ~30 days per the consumer help page) and the id should become free for a fresh `events.insert` after that. Within that window, a re-run of the job will hit 409 on that id every time, and the job's error handling must explicitly decide, on 409, whether to leave the tombstone alone (respecting the user's deletion) or revive it (patch `status` back to `confirmed`, treating Garmin as the source of truth). The Calendar API does not make this choice on the job's behalf — both a "reappear" and a "stay deleted forever within the trash window" outcome are possible depending on which branch the job's 409-handler takes, and this needs to be a deliberate decision written into the sync logic, not an assumption.

---

## Confidence

| # | Answer | Confidence | Reason |
|---|--------|-----------|--------|
| 1 | Charset `a-v0-9`, length 5–1024, unique per calendar | **High** | Verbatim, identical text in both the human-readable reference page and the live machine-readable Discovery Document — as primary as sources get. |
| 2 | Type-tag-letter + digits, no separators, is a conforming deterministic-id scheme | **High** | Directly derived from the Q1 character-class rule; the scheme itself was not tested live against the API, but the rule it's built on is unambiguous and doc-quoted. |
| 3 | 409 `duplicate` on insert-with-existing-id; insert-then-409-then-patch is the right create-or-update pattern; import is a different, `iCalUID`-keyed mechanism not suited to this job | **High** | The 409/`duplicate` behavior and its official remediation ("...or use the events.update method") are directly quoted from Google's own error-handling guide, and the import/insert distinction is confirmed from the live Discovery Document's parameter list (no `sendUpdates` on import; `iCalUID` required). |
| 4 | Patch preserves unspecified fields, update can clobber them; sendUpdates=none can still leak some email; UI position/notification-to-owner specifics | **Medium** | The patch-vs-update data-safety claim is directly quoted from both reference pages (high confidence on that half). The "some emails might still be sent" caveat is directly quoted too. But UI reordering, colour-reset-on-patch (only inferred from patch's general contract, no reminders/colorId-specific worked example), and owner-side (non-guest) notification behavior are all points the docs stay silent on, pulling the combined confidence down to medium. |
| 5 | Deletion is a tombstone (status=cancelled), reinsert hits 409, tombstone "eventually disappears" but no API-documented retention period; revival mechanism (patch status→confirmed) is logical but not spelled out with a worked example | **Medium** | The tombstone-persists and reinsert-409 behaviors are strongly grounded in official doc text (status field) plus consistent, dated community reproduction (GitHub issue, 2020-03-20). The exact retention/reuse timeline (~30 days) comes from the consumer help center, not the API reference, and the precise "how to revive via patch" mechanism is corroborated only by an unanswered 2014-06-16 community mailing-list post, not an official worked example — hence medium rather than high. |
