"""Google Calendar writes for the Timeline Sync.

The write semantics are the whole point of this module. Every write is an
`events.insert` carrying a deterministic id, falling back to `events.patch`
on the documented `409 duplicate`. Neither path needs a prior `get`, because
patching `status` is idempotent — a live event is untouched by it and a
tombstoned one is revived. See ADR 0006.

`patch` is used rather than `update`: `update` is a full PUT that silently
clobbers a hand-made edit, and the same Sleep event is rewritten up to seven
mornings running.
"""

import json

SCOPES = ["https://www.googleapis.com/auth/calendar"]

INSERTED = "inserted"
PATCHED = "patched"


class TimelineCalendarClient:
    def __init__(self, service_account_json, calendar_id, service=None):
        self.calendar_id = calendar_id
        self._service = service if service is not None else _build(service_account_json)

    def insert_or_patch(self, event_id, body, patch_body):
        """Insert the event, or patch it if the id is already taken.

        `patch_body` is what gets written on a 409. For an Activity it is
        `{"status": "confirmed"}` alone, so content is never rewritten and
        append-only holds; for Sleep it is the full field set plus status.
        """
        events = self._service.events()
        try:
            events.insert(
                calendarId=self.calendar_id,
                body={**body, "id": event_id},
                sendUpdates="none",
            ).execute()
            return INSERTED
        except Exception as error:  # HttpError, but keep the stub seam simple
            if _status_of(error) != 409:
                raise
            events.patch(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=patch_body,
                sendUpdates="none",
            ).execute()
            return PATCHED


def _status_of(error):
    response = getattr(error, "resp", None)
    status = getattr(response, "status", None)
    return int(status) if status is not None else None


def _build(service_account_json):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)
