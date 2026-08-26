# Garmin sleep, nap, and activity response shapes (`python-garminconnect`)

Researched against the live `cyberjunky/python-garminconnect` GitHub repo
(`master` branch, `pushed_at: 2026-08-22T06:42:56Z`, package version
`0.3.12` per `pyproject.toml`). All source excerpts below were fetched
directly via `curl` from `raw.githubusercontent.com` and read verbatim —
line numbers refer to the fetched copies.

**Important correction to the task's framing:** this current version of
`python-garminconnect` does **not** depend on `garth` at all. Its
`pyproject.toml` dependencies are `curl_cffi`, `requests`, `ua-generator` —
no `garth`. The HTTP/auth layer is now a bundled, self-written module
(`garminconnect/client.py`, 1736 lines) implementing its own multi-strategy
SSO login (mobile app flow, SSO widget flow, web portal flow) and DI OAuth
token exchange. So "the underlying `garth` HTTP layer" mentioned in the task
brief does not apply to the installed dependency surface of this repo's
target version — everything below is sourced from `garminconnect/__init__.py`,
`garminconnect/client.py`, and `garminconnect/typed.py` directly. (Note this
repo's own local `run_page/garmin_sync.py` also does not use
`python-garminconnect` — it hand-rolls its own tiny `Garmin` class on top of
`garth` + `httpx`. Only `run_page/garmin_publication_client.py` uses the real
`from garminconnect import Garmin`.)

---

## Verdict

1. **Sleep methods:** `Garmin.get_sleep_data(cdate: str) -> dict[str, Any]`
   hits `GET /wellness-service/wellness/dailySleepData/{displayName}?date={cdate}&nonSleepBufferMinutes=60`
   and is the one method with a confirmed field-level shape (via the
   library's own Pydantic model in `typed.py`, backed by a test fixture).
   It returns a nested `dailySleepDTO` object with **both** GMT and Local
   start/end fields: `sleepStartTimestampGMT` / `sleepEndTimestampGMT` /
   `sleepStartTimestampLocal` / `sleepEndTimestampLocal`, all typed as
   `int | None` — **epoch milliseconds** (confirmed by a real sample value
   `1761100200000` in the test fixture — 13 digits, ms since epoch). The
   library's own docstring explicitly warns that `*Local` fields have been
   reported (in a linked GitHub issue) to be double-offset for some
   CN/UTC+8 accounts, and recommends using the `*GMT` fields and converting
   to local time yourself. There's a second, lighter method,
   `get_sleep_daily(start, end) -> list[dict]`, hitting
   `/sleep-service/stats/sleep/daily/{start}/{end}` (28-day chunking done
   client-side) — but its confirmed fields are only `calendarDate` and
   (per a test mock) `overallSleepScore`; **no timestamp fields for this
   method are confirmed anywhere in source** — see Confidence notes.

2. **Naps are NOT distinct per-nap records with individual timestamps
   anywhere in this library.** `DailySleepDTO` (the `get_sleep_data` shape)
   has a single field `napTimeSeconds` (alias `napTimeSeconds`, confirmed
   in both `typed.py` and the test fixture, sample value `0`) — this is a
   **total nap duration in seconds for the day**, with no start/end, no
   count, no array. There is no `get_naps` method, no nap-specific
   endpoint, and no per-nap array anywhere in `__init__.py`'s ~150 `get_*`
   methods. The only other place "nap" appears in the whole codebase is a
   docstring on `get_body_battery_events(cdate)` (hits
   `/wellness-service/wellness/bodyBattery/events/{cdate}`): *"Events can
   include sleep, recorded activities, auto-detected activities, and
   naps."* This implies Garmin's body-battery-events endpoint may carry
   individual nap events with their own timing, but **the library gives no
   field names for this at all** — the method returns
   `list[dict[str, Any]]` untyped, with no model, no test asserting a nap
   shape, and no demo.py code that inspects a per-event `eventType` or
   similar discriminator field. **This must be treated as an open question,
   not a confirmed field shape** — see item 2 in Confidence.
   → **Design implication:** if per-nap calendar events with individual
   start/end are required, `get_sleep_data`'s `napTimeSeconds` cannot
   supply them (aggregate-only). The only lead is the unmodeled
   `get_body_battery_events` payload, which would need to be fetched and
   inspected against a real account before any field names can be trusted.

3. **Summary metrics on `get_sleep_data`'s `dailySleepDTO`** (all
   confirmed via `typed.py` + the test fixture):
   - `sleepTimeSeconds`, `napTimeSeconds` — durations, seconds
   - `deepSleepSeconds`, `lightSleepSeconds`, `remSleepSeconds`,
     `awakeSleepSeconds` — stage durations, seconds
   - `sleepWindowConfirmed` — bool
   - `avgSleepHRV` — float
   - `avgSpO2` — float (blood oxygen)
   - `avgRespirationValue`, `lowestRespirationValue`,
     `highestRespirationValue` — float, breaths/min
   - `sleepScores` — nested object: `overall` (`{value, qualifierKey}`),
     plus sub-scores `totalDuration`, `stress`, `awakeCount`,
     `remPercentage`, `restlessness`, `lightPercentage`, `deepPercentage`
     (each the same `{value, qualifierKey}` shape). Test fixture confirms
     `sleepScores.overall.value == 84` as a real-shaped sample.
   - **No resting-heart-rate field lives inside the sleep response** —
     RHR is a separate call (`get_rhr_day` / `get_stats`, field
     `restingHeartRate`, confirmed in `typed.DailyStats`).
   - Note: `get_sleep_data` also returns large per-minute arrays (HR,
     movement, SpO2 time series) that `typed.py` deliberately does *not*
     model ("large and rarely needed in typed form") — their field names
     are not established here.

4. **`get_activities(start=0, limit=20, activitytype=None)`** hits
   `GET /activitylist-service/activities/search/activities?start=..&limit=..[&activityType=..]`.
   Passing `activitytype=None` (the default) simply omits the
   `activityType` query param entirely (source: `if activitytype:
   params["activityType"] = activitytype`) — this returns **all activity
   types** unfiltered, no unexpected behavior. `limit` is capped at
   `MAX_ACTIVITY_LIMIT = 1000` (raises `ValueError` above that).
   A related method, `get_activities_by_date(startdate, enddate=None,
   activitytype=None, sortorder=None)`, auto-paginates the *same* endpoint
   in pages of 20 (capped at `MAX_PAGINATED_REQUESTS = 2000` requests) and
   documents valid `activitytype` values in its docstring: `cycling,
   running, swimming, multi_sport, fitness_equipment, hiking, walking,
   other` (coarse top-level categories — sub-types like
   `trail_running`/`treadmill_running` show up in the per-activity
   `activityType.typeKey` field, not as a filter value here).
   Per-item fields **confirmed via `typed.Activity`** (which models
   `get_activities_by_date`'s items and, per source, the same activity
   list shape as `get_activities`):
   - `activityId`, `activityName`
   - `startTimeLocal`, `startTimeGMT` — both **strings** (not epoch ints,
     unlike sleep's timestamps) — see Confidence for the exact format
     caveat
   - `activityType` → nested `{typeId, typeKey, parentTypeId, isHidden}`
   - `duration`, `movingDuration`, `elapsedDuration` — floats (seconds,
     by strong convention, though the model doesn't annotate units)
   - `distance`, `elevationGain`, `elevationLoss`
   - `averageSpeed`, `maxSpeed`
   - `averageHR` (model attr `average_hr`), `maxHR`
   - `calories`, `bmrCalories`
   - `avgPower`, `maxPower`, `normPower`
   - `aerobicTrainingEffect`, `anaerobicTrainingEffect`,
     `activityTrainingLoad`, `trainingEffectLabel`
   - `averageRunningCadenceInStepsPerMinute`,
     `maxRunningCadenceInStepsPerMinute`
   - Strength-specific: `totalSets`, `activeSets`, `totalReps`,
     `totalVolume` (null for non-strength activities)
   All of the above are available **directly in the list response** — no
   per-activity detail fetch (`get_activity(activity_id)`) is needed to
   populate a calendar description with duration/distance/HR/calories.
   `elapsedDuration` vs `movingDuration` are both present distinctly, so
   "elapsed vs moving time" is directly answerable.

5. **Rate limits / pagination:**
   - **Sleep is one-day-per-call** for the endpoint with confirmed
     timestamp fields (`get_sleep_data`) — a 7-day window needs 7 calls, a
     30-day backfill needs 30 calls. `get_sleep_daily(start, end)` *is* a
     genuine date-range method (auto-chunks at Garmin's 28-day-per-request
     server limit) but its confirmed fields don't include start/end
     timestamps, so it is not a substitute for building calendar events
     — only useful for score trending if that's ever wanted alongside.
   - **Activities support real date-range pagination**
     (`get_activities_by_date`), so a 7-day or 30-day activity backfill is
     1 logical call (internally paginated in pages of 20, capped at 2000
     pages = effectively unbounded for this use case).
   - The library's own `connectapi()` (used by nearly every `get_*`
     method) is wrapped in `@_handle_api_errors("API call")`
     (`__init__.py` line 647), which:
     - Translates HTTP 401 → `GarminConnectAuthenticationError` (fails
       fast, no retry)
     - Translates HTTP 429 → `GarminConnectTooManyRequestsError`
       (**fails fast, never retried** — by explicit design comment:
       "Never retries 401 (auth), 429 (rate-limit) or 4xx (client) errors
       — those are deterministic and caller-actionable")
     - Retries only 5xx / raw network errors, up to `retry_attempts`
       (default 3), with exponential backoff + 50–100% jitter between
       `retry_min_wait` (1.0s) and `retry_max_wait` (10.0s)
   - **No built-in throttle/delay between successive data-fetch calls** —
     the library does not self-rate-limit `get_sleep_data`/`get_activities`
     calls; a caller doing 7 or 30 sequential `get_sleep_data` calls gets
     no automatic spacing. Nothing in source states a numeric
     requests-per-minute ceiling for data endpoints, and a community
     GitHub issue asking exactly this
     ([python-garminconnect#26](https://github.com/cyberjunky/python-garminconnect/issues/26))
     went unanswered with no published number.
   - **The aggressive, well-documented rate limiting in this codebase is
     almost entirely about the *login/SSO* flow, not data fetching.**
     `client.py` implements multiple login strategies (mobile app flow +
     SSO widget flow + web portal flow, each with/without TLS
     impersonation) specifically because Garmin's Cloudflare-fronted SSO
     endpoints 429 aggressively and the rate limit is **per-account**, not
     per-IP (confirmed by community reports below) — changing network or
     headers does not help once triggered.
   - **Community-reported soft-ban behavior** (via GitHub issue search,
     not verified in source):
     - [#337](https://github.com/cyberjunky/python-garminconnect/issues/337) —
       429 on the OAuth-preauthorized login endpoint.
     - [#344](https://github.com/cyberjunky/python-garminconnect/issues/344) —
       reports the SSO rate limit is keyed on `clientId` + account email
       (i.e., **per-account**, not per-IP/User-Agent), and describes it as
       persisting regardless of network/header changes; this is what
       motivated the SSO-widget fallback strategy now in `client.py`.
     - Garmin forums thread "Persistent 429 on API login — account blocked
       for 48+ hours" — anecdotal reports of accounts staying 429-blocked
       for 48+ hours after triggering the limit (login flow specifically).
   - **Practical implication for the described job** (daily 7-day window +
     one 30-day backfill): login/auth is the fragile part — do it once per
     job run and cache/reuse the token (which is exactly what this repo's
     `garmin_publication_client.py` already does via a tokenstore).
     Data-fetch calls themselves (`get_sleep_data` × N days,
     `get_activities_by_date` × 1 call) are comparatively low-risk and have
     no documented hard ceiling, but should still not be assumed
     unlimited — the library's own 429-fail-fast design implies the
     authors expect callers to handle `GarminConnectTooManyRequestsError`
     on any call, sleep or activity alike.

---

## Source references

- `garminconnect/__init__.py` (raw, `master`, 3743 lines) —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/garminconnect/__init__.py
  - `get_sleep_data`: lines 1877–1891
  - `get_sleep_daily`: lines 1893–1929 (28-day chunking, endpoint
    `/sleep-service/stats/sleep/daily/{start}/{end}`)
  - `garmin_connect_daily_sleep_url` definition: lines 480–482
    (`/wellness-service/wellness/dailySleepData`)
  - `get_body_battery_events`: lines 1373–1381; url def line 490–492
    (`/wellness-service/wellness/bodyBattery/events`)
  - `get_activities`: lines 2334–2359 (endpoint def line 551–553:
    `/activitylist-service/activities/search/activities`;
    `MAX_ACTIVITY_LIMIT = 1000` at line 40)
  - `get_activities_by_date`: lines 2624–2677
    (`MAX_PAGINATED_REQUESTS = 2000` at line 47)
  - `get_activities_fordate`: lines 2368–2374 — **note:** its backing URL
    constant `garmin_connect_activity_fordate` (line 558) is literally set
    to `/mobile-gateway/heartRate/forDate`, which looks like a heart-rate
    endpoint, not an activities endpoint. Flagged verbatim from source as
    a naming/wiring oddity worth independently verifying before relying on
    this method for "activities on date X."
  - `connectapi` + `@_handle_api_errors` decorator (429/401/5xx handling,
    retry/backoff logic): lines 224–370 (decorator), 647–650 (`connectapi`)
  - `_validate_date_range`: line 84
- `garminconnect/typed.py` (raw, `master`, 594 lines) —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/garminconnect/typed.py
  - `DailySleepDTO` / `SleepScores` / `SleepScoreValue` / `SleepData`:
    lines 160–239 (this is the highest-confidence field list in this
    report — an explicit, maintained Pydantic schema with `extra="allow"`
    for forward-compat)
  - `Activity` / `ActivityType`: lines 387–453
- `garminconnect/client.py` (raw, `master`, 1736 lines) —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/garminconnect/client.py
  - No `garth` import; confirms self-contained HTTP/auth layer
  - `_run_request` (generic error translation for data calls, 401 auto-retry
    with refresh, 4xx → `GarminConnectConnectionError`/`NotFoundError`):
    lines ~1636–1733
  - Login-flow rate-limit handling (multiple 429-aware strategies for
    mobile/widget/portal SSO flows): lines throughout ~480–1350 (see grep
    hits for "429"/"rate limit")
- `pyproject.toml` —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/pyproject.toml
  - `dependencies = ["curl_cffi>=0.15.0", "requests>=2.33.0",
    "ua-generator>=1.0"]` — no `garth`
- `tests/test_typed.py` —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/tests/test_typed.py
  - `SAMPLE_SLEEP_DATA` fixture (lines ~80–100): real-shaped sample with
    `sleepStartTimestampGMT: 1761100200000` (13-digit ms epoch),
    `napTimeSeconds: 0`, `sleepScores.overall.value: 84`, etc. — the
    concrete evidence behind item 1 and item 3's field list.
- `tests/test_garmin_unit.py` —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/tests/test_garmin_unit.py
  - Confirms `get_sleep_data` endpoint routing (line ~465):
    `("get_sleep_data", ("2026-03-15",), "/wellness-service/wellness/dailySleepData")`
  - Confirms `get_sleep_daily` URL + chunking/dedup/sort behavior (lines
    ~1424–1465), using mock rows `{"calendarDate": ..., "overallSleepScore":
    ...}` — but this is test-mock data for exercising the chunking logic,
    not a verified real-API field dump, so `overallSleepScore` should be
    treated as plausible-but-unconfirmed (see Confidence).
- `demo.py` (raw, `master`, 4929 lines) —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/demo.py
  - Confirms `dailySleepDTO`, `sleepTimeSeconds`, `deepSleepSeconds` usage
    (lines 1004–1019)
  - Confirms activity list fields actually read in display code:
    `activityName`, `activityType.typeKey`, `startTimeLocal`, `duration`,
    `distance`, `calories`, `avgHR`, `activityId` (lines ~1108–1130,
    1760–1762, 3714–3716) — a subset of the fuller `typed.Activity` list,
    useful as independent cross-confirmation of the core fields.
- `README.md` —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/README.md
  - No documented numeric rate limit; documents the multi-strategy
    resilient login and the cached-token self-healing behavior (matches
    what this repo's `garmin_publication_client.py` already relies on).
- `example.py` —
  https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/example.py
  - Minimal; confirms `GarminConnectTooManyRequestsError` is the exception
    type callers are expected to catch for 429s, and treats it as
    fail-immediately ("Rate limit: ... sys.exit(1)"), not retry-with-backoff,
    reinforcing that 429 handling is a caller responsibility.
- Community-reported rate-limit behavior (via web search, not source —
  cited for the "documented or community-reported" part of Q5):
  - https://github.com/cyberjunky/python-garminconnect/issues/337
  - https://github.com/cyberjunky/python-garminconnect/issues/344
  - https://github.com/cyberjunky/python-garminconnect/issues/26
  - https://forums.garmin.com/developer/fit-sdk/f/discussion/435087/persistent-429-on-api-login-account-blocked-for-48-hours

---

## What could NOT be established from sources (do not guess these)

- **Exact field names for individual nap events**, if Garmin's
  `bodyBattery/events` endpoint indeed carries them per the library's own
  docstring hint. No model, no test fixture, no demo.py field access
  exists for this endpoint's item shape in the library. If per-nap
  start/end is a hard requirement, this endpoint needs to be fetched
  against a real account and inspected directly before any field name
  (`eventType`, `startTime`, whatever) is encoded into a design.
- **Exact string format of `startTimeLocal`/`startTimeGMT` on activities**
  (e.g. `"2026-03-15 07:15:23"` vs `"2026-03-15T07:15:23.0"`). `typed.py`
  types them as plain `str` with no format validator; `demo.py`'s own
  display code does `activity.get("startTimeLocal", "").split("T")[0]`,
  which only implies the author *expects* a `T` separator but doesn't
  prove it — no regex/strptime pattern for this field exists anywhere in
  the fetched source. A different part of the library
  (`create_manual_activity`) sends `startTimeLocal` in the pattern
  `"2023-12-02T10:00:00.000"` when *writing* an activity, which is at
  least suggestive for the *read* shape too, but this is a write-payload
  convention, not a confirmed read-response format.
  **`get_sleep_data`'s timestamps, by contrast, are unambiguous** — typed
  as `int` and demonstrated as 13-digit millisecond epoch values in the
  test fixture — so if your design needs a totally unambiguous timestamp
  representation, treat sleep timestamps as solid and treat activity
  timestamp *string formatting* as needing a live-account confirmation
  pass before you hard-code a parser.
- **`get_sleep_daily`'s full field list beyond `calendarDate` and
  `overallSleepScore`.** Only these two field names appear anywhere in
  source (and only inside a unit test's mock return value, not a real
  fixture or a Pydantic model) — no confirmation of whether stage
  durations, sleep-score sub-components, or timestamps are present on
  this range endpoint's per-day rows.
- **Any numeric rate-limit threshold** (requests/minute or /hour) for
  Garmin Connect's data endpoints. Neither the source nor any linked
  community issue states one; the working assumption from the library's
  own design (429 = fail-fast, caller-handled) is that none is published
  and callers are expected to react to `GarminConnectTooManyRequestsError`
  reactively rather than plan around a known ceiling.

---

## Confidence

1. **Sleep methods / timestamps — High.** Endpoint, param name, and the
   `sleepStartTimestampGMT`/`sleepEndTimestampGMT`/`*Local` field names +
   millisecond-epoch typing are confirmed by three independent source
   artifacts: the method's own docstring, the maintained `typed.py`
   Pydantic model, and a concrete sample value in `test_typed.py`
   (`1761100200000`). `get_sleep_daily`'s endpoint and 28-day chunking
   logic are High confidence (directly read); its field list beyond
   `calendarDate`/`overallSleepScore` is unconfirmed (Low).

2. **Naps — Medium-High on the negative claim, Low on any positive nap
   field shape.** High confidence that `napTimeSeconds` is an
   aggregate-only daily total with no per-nap timing anywhere in the
   `get_sleep_data` shape (directly modeled + fixture-confirmed). Low
   confidence on whether/how `get_body_battery_events` actually surfaces
   individual naps with timestamps — the only evidence is one docstring
   sentence, with zero field names, zero test coverage, and zero demo.py
   usage of a nap-identifying field.

3. **Summary metrics — High.** All field names come directly from the
   maintained `typed.py` model plus a real-shaped test fixture with
   sample values, cross-confirmed by `demo.py`'s independent field access
   for the subset it uses (`sleepTimeSeconds`, `deepSleepSeconds`).

4. **Activities — High for endpoint, pagination, `activitytype=None`
   behavior, and the field list (all confirmed via `typed.Activity` +
   independent `demo.py` field access). Medium for the exact
   `startTimeLocal`/`startTimeGMT` string format**, since no
   parser/regex/format-validator for these fields exists in source — only
   suggestive, not conclusive, evidence for the separator/format used.

5. **Rate limits — High for the library's own retry/backoff/429-handling
   code** (read directly, unambiguous). **Medium for the
   login-vs-data-fetch distinction and the "per-account, not per-IP"
   characterization** — this rests on community GitHub issues, not
   Anthropic-verifiable Garmin documentation (Garmin publishes no public
   rate-limit spec), so treat it as credible community consensus rather
   than a hard guarantee. **Low/none for any numeric threshold** — none
   exists in any source consulted, confirmed explicitly by an unanswered
   community question asking for exactly that number.
