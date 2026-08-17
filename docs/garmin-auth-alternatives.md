# Garmin Auth Alternatives

Date: 2026-08-10

Status: Implemented for the active Garmin Publication path. The legacy generic
Garmin sync/upload scripts still use `garth` and `GARMIN_SECRET_STRING`.

## Context

The legacy Garmin path still imports `garth` directly in
`run_page/garmin_sync.py`. It loads `GARMIN_SECRET_STRING` through
`garth.client.loads(...)`, refreshes `garth.client.oauth2_token`, then calls
Garmin Connect endpoints with that bearer token.

The active archive-first publication path now uses
`run_page/garmin_publication_client.py`, which wraps
`cyberjunky/python-garminconnect` and reads `GARMIN_TOKENS_JSON`.

The publication path depends on only two read capabilities from that wrapper:

- list activities, optionally filtered to running:
  `activitylist-service/activities/search/activities`
- download the original activity archive and extract the FIT:
  `download-service/files/activity/{activity_id}`

`garth` is now the weak point. Its PyPI page says it is deprecated and no
longer maintained because Garmin changed the auth flow, and that new logins no
longer work. It also says existing saved OAuth1 sessions may continue only until
that token expires.

Sources:

- [garth on PyPI](https://pypi.org/project/garth/)
- [run_page/garmin_sync.py](../run_page/garmin_sync.py)
- [run_page/garmin_publish.py](../run_page/garmin_publish.py)

## Current Repo Constraints

- `run_page/garmin_sync.py` is async and uses `httpx.AsyncClient`, but the
  Garmin surface itself is small.
- `run_page/garmin_publish.py` imports `GarminPublicationClient`, calls
  `get_activities(...)`, then `download_activity(..., "fit")`.
- `.github/workflows/garmin_publication.yml` now runs Python 3.12 because
  current `garminconnect` requires Python >= 3.12.
- `.github/workflows/ci.yml` still tests Python 3.9, 3.10, 3.11, and 3.12.
- `requirements.txt` installs `garminconnect==0.3.8` on Python >= 3.12.
- `requirements.txt` still keeps `garth` for inactive legacy Garmin scripts.

## Options

### 1. `cyberjunky/python-garminconnect`

Repository: <https://github.com/cyberjunky/python-garminconnect>

PyPI: <https://pypi.org/project/garminconnect/>

Current fit:

- Best near-term replacement for this repo's current custom wrapper.
- It is the project this repo originally copied from.
- It supports activity listing through `get_activities(...)`.
- It supports activity downloads through `download_activity(...)`.
- For original downloads, its source says `ActivityDownloadFormat.ORIGINAL`
  returns the original ZIP content and leaves extraction to the caller.

Auth status:

- Since `0.3.0`, it replaced the `garth` dependency with a native auth engine.
- Current source dependencies are `curl_cffi`, `requests`, and `ua-generator`,
  not `garth`.
- Auth stores DI OAuth bearer tokens in `~/.garminconnect/garmin_tokens.json`.
- MFA is supported through `prompt_mfa` and `return_on_mfa`.
- Tokens are auto-refreshed before API requests.
- It has multiple login strategies and token validation fallback for Garmin's
  changing SSO behavior.

Python and dependency impact:

- PyPI/project metadata requires Python >= 3.12.
- This conflicts with the repo-wide CI matrix and with the Garmin Publication
  workflow's current Python 3.10 runtime.
- A migration would likely need to either:
  - raise Garmin-specific workflows to Python 3.12 and avoid installing
    `garminconnect` on Python 3.9-3.11 CI jobs, or
  - raise the whole repo's supported Python floor.

Migration risk:

- Medium.
- The API shape is close, but the auth artifact changes from this repo's
  existing `GARMIN_SECRET_STRING` to `garmin_tokens.json`.
- Existing GitHub secret material would need to be regenerated or converted.
- The library is still unofficial and can break if Garmin changes internal web
  endpoints, but it is actively maintaining the post-`garth` auth path.
- This is the recommended candidate for a code migration.

Sources:

- [python-garminconnect README](https://github.com/cyberjunky/python-garminconnect)
- [python-garminconnect pyproject](https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/pyproject.toml)
- [python-garminconnect client.py](https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/garminconnect/client.py)
- [python-garminconnect Garmin class](https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/garminconnect/__init__.py)
- [python-garminconnect releases](https://github.com/cyberjunky/python-garminconnect/releases)

### 2. `garmin-auth`

Repository: <https://github.com/drkostas/garmin-auth>

PyPI: <https://pypi.org/project/garmin-auth/>

Current fit:

- Useful as an auth/session wrapper, not as a complete Garmin activity client.
- Its Python API returns an authenticated `garminconnect.Garmin` client.
- It can call `client.get_activities(...)` after login because it delegates to
  `python-garminconnect`.

Auth status:

- Does not depend on `garth`.
- Wraps `garminconnect>=0.3.0`.
- Adds token persistence, MFA resume support, 429-aware retry/backoff, and
  optional PostgreSQL token storage.
- Token format is the new `garmin_tokens.json`, explicitly not compatible with
  old `garth` token storage.

Python and dependency impact:

- Requires Python >= 3.10 according to PyPI metadata.
- Because it depends on `garminconnect>=0.3.0`, the effective runtime may still
  be constrained by `garminconnect`'s Python >= 3.12 requirement unless versions
  are carefully pinned and tested.

Migration risk:

- Medium to high if used as the main dependency, because it introduces another
  layer around `python-garminconnect`.
- Lower value for this repo than using `python-garminconnect` directly unless
  we specifically need DB-backed token storage or a richer auth CLI for CI.

Sources:

- [garmin-auth on PyPI](https://pypi.org/project/garmin-auth/)
- [garmin-auth repository](https://github.com/drkostas/garmin-auth)

### 3. `garmin-py`

Repository: <https://github.com/ching-kuo/garmin-py>

PyPI: <https://pypi.org/project/garmin-py/>

Current fit:

- CLI/MCP product for extracting Garmin data and exposing it to AI assistants.
- It includes `activity download`; the default format is original, which is the
  FIT file inside a ZIP archive.
- It authenticates via the maintained `python-garminconnect` backend.

Auth status:

- Does not use `garth` as the active auth backend.
- Keeps `GARTH_HOME` only as a deprecated compatibility alias.
- Stores sessions as `garmin_tokens.json` under `GARMIN_HOME` /
  `~/.garminconnect`.
- Supports MFA flow in the MCP/CLI UX.

Python and dependency impact:

- Requires Python >= 3.10 according to PyPI metadata.
- It is a CLI/MCP layer, so using it from this repo's Python pipeline would
  likely mean shelling out or adopting a larger abstraction than needed.

Migration risk:

- High for direct integration into this repo.
- It is better as a manual/admin tool or reference implementation than as the
  production library behind `run_page/garmin_publish.py`.

Sources:

- [garmin-py on PyPI](https://pypi.org/project/garmin-py/)
- [garmin-py repository](https://github.com/ching-kuo/garmin-py)

### 4. `garmin-health-data`

Repository: <https://github.com/diegoscarabelli/garmin-health-data>

PyPI: <https://pypi.org/project/garmin-health-data/>

Current fit:

- CLI/ETL package that downloads Garmin health and activity data into local
  files and SQLite.
- It can download activity files in FIT or TCX format and preserve raw files on
  disk.
- It ships a self-contained Garmin client instead of depending on a third-party
  Garmin Connect client.

Auth status:

- Does not depend on `garth`.
- Uses its own SSO/MFA login client with several strategies and deliberate
  anti-rate-limit delays.
- Stores per-account `garmin_tokens.json` under `~/.garminconnect/<user_id>/`.
- Tokens auto-refresh if extraction runs at least once within the refresh-token
  lifetime.

Python and dependency impact:

- Requires Python >= 3.10.
- Depends on `curl-cffi`, `requests`, `ua-generator`, `fitdecode`, SQLAlchemy,
  and CLI/data-pipeline packages.

Migration risk:

- High for this repo's current code path.
- It is a full ETL/database pipeline, not a small API wrapper.
- It may be useful as a reference for post-`garth` auth and FIT download
  behavior, but integrating it directly would duplicate this repo's existing
  storage and publication pipeline.

Sources:

- [garmin-health-data README](https://github.com/diegoscarabelli/garmin-health-data)
- [garmin-health-data pyproject](https://raw.githubusercontent.com/diegoscarabelli/garmin-health-data/main/pyproject.toml)
- [garmin-health-data on PyPI](https://pypi.org/project/garmin-health-data/)

### 5. Official Garmin Connect Activity API

Documentation: <https://developer.garmin.com/gc-developer-program/activity-api/>

Current fit:

- This is the only official option found.
- Garmin documents access to activity details and activity files in FIT, GPX,
  and TCX formats.
- Access requires approval and an evaluation environment.

Auth status:

- Official consent-based API, not reverse-engineered web/mobile login.
- The public page does not provide a drop-in personal OAuth flow suitable for a
  private GitHub Actions runner without applying to the developer program.

Python and dependency impact:

- No Python library requirement from Garmin's public page.
- A migration would require a new integration model and likely credentials from
  Garmin's program.

Migration risk:

- High for near-term personal use because access approval is external.
- Best long-term stability if approved, because it avoids scraping or private
  Garmin Connect endpoints.

Sources:

- [Garmin Connect Activity API](https://developer.garmin.com/gc-developer-program/activity-api/)

## Not Recommended

### `garminexport`

Repository/PyPI: <https://pypi.org/project/garminexport/>

It can back up activity exports, including FIT, GPX, and TCX, and supports MFA,
but its PyPI documentation says authentication is handed to `garth`. Because the
goal is to move away from `garth`, it is not a viable replacement for this repo.

## Implemented Migration

The active Garmin Publication workflow now uses `python-garminconnect`:

- `run_page/garmin_publish.py prepare` reads `GARMIN_TOKENS_JSON`.
- `run_page/garmin_publication_client.py` loads the tokenstore into
  `garminconnect.Garmin`.
- `get_activities(start, limit)` maps to
  `Garmin.get_activities(..., activitytype="running")`.
- `download_activity(activity_id, "fit")` maps to
  `Garmin.download_activity(..., ActivityDownloadFormat.ORIGINAL)`.
- `.github/workflows/garmin_publication.yml` runs Python 3.12 and passes
  `secrets.GARMIN_TOKENS_JSON`.

Generate the tokenstore with Python 3.12+:

```bash
python run_page/get_garmin_tokens.py "$GARMIN_EMAIL" --tokenstore .garminconnect --print-secret
```

Then set the printed JSON as the GitHub Actions secret:

```bash
gh secret set GARMIN_TOKENS_JSON --repo zhengfran/running_page
```

Do not commit `.garminconnect/garmin_tokens.json`; it contains a refresh token.

### Token self-heal (`GARMIN_EMAIL` / `GARMIN_PASSWORD`)

`GARMIN_TOKENS_JSON` can go stale (Garmin revokes or expires the cached
session) and the workflow has failed silently for days on a bare 401 before
(2026-08-13 through 2026-08-16). `garminconnect==0.3.8`'s `Garmin.login()`
already handles this: it tries the cached tokenstore first, and only if the
API rejects that token does it discard it and fall back to a fresh
username/password login — but only when `Garmin()` was constructed with
credentials.

`run_page/garmin_publication_client.py` now accepts optional `email`/
`password` and forwards them into `Garmin(...)`, and
`run_page/garmin_publish.py` reads them from the optional `GARMIN_EMAIL` /
`GARMIN_PASSWORD` env vars. Set these as GitHub Actions secrets (same account
as `GARMIN_TOKENS_JSON`) to get automatic recovery from a stale token without
manual secret rotation:

```bash
gh secret set GARMIN_EMAIL --repo zhengfran/running_page
gh secret set GARMIN_PASSWORD --repo zhengfran/running_page
```

Caveats:

- Only safe if the account does **not** require MFA at login — the library's
  `prompt_mfa` callback can't be answered headlessly in CI, so an MFA
  challenge still hard-fails (with a clearer error pointing back at
  `get_garmin_tokens.py`).
- The refreshed token isn't written back to `GARMIN_TOKENS_JSON` (that would
  need a secrets-write-scoped PAT in the workflow, which is a bigger secret
  to hold than the password itself). This is intentionally accepted: since
  the fallback only fires when the cached token is rejected, it costs one
  extra SSO login per run for at most the days between a token going stale
  and someone rotating `GARMIN_TOKENS_JSON` by hand — not a full login every
  run.
- Storing the raw account password is a larger blast radius than a scoped
  session token if the secret ever leaks. Weigh that against the cost of
  another silent multi-day outage.

## Recommendation

Use `cyberjunky/python-garminconnect` as the active publication client.

The smallest practical migration is:

1. Provision `GARMIN_TOKENS_JSON` in GitHub Actions.
2. Run a manual Garmin Publication dry run with `publish=false`.
3. If the dry run succeeds, run a manual publication with `publish=true`.
4. After live validation, migrate or remove the inactive legacy Garmin scripts
   that still depend on `garth`.

Do not migrate to `garmin-auth`, `garmin-py`, or `garmin-health-data` first
unless the project goal changes from a small publication pipeline to a broader
Garmin CLI/session-management system.
