"""Google Calendar writes for the Timeline Sync.

The Timeline is written into the owner's LifeOS Time Log, a calendar the
owner also fills by hand. Every write is an `events.insert` carrying a
deterministic id. On the documented `409 duplicate` the existing event is
read once and touched only when it carries this sync's Source Marker and is
still live; a hand-made event, or one the owner deleted, is left alone. See
ADR 0010 (which refines ADR 0006).

`patch` is used rather than `update`: `update` is a full PUT that silently
clobbers a hand-made edit, and the same Sleep event is rewritten up to seven
mornings running.
"""

import json

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

INSERTED = "inserted"
PATCHED = "patched"
UNCHANGED = "unchanged"
SKIPPED_DELETED = "skipped_deleted"
SKIPPED_FOREIGN = "skipped_foreign"
OUTCOMES = (INSERTED, PATCHED, UNCHANGED, SKIPPED_DELETED, SKIPPED_FOREIGN)


class TimelineCalendarClient:
    def __init__(self, service_account_json, calendar_id, service=None):
        if not calendar_id:
            raise ValueError("A target calendar id is required")
        self.calendar_id = calendar_id
        self._service = service if service is not None else _build(service_account_json)

    def insert_or_patch(self, event_id, body, patch_body, marker):
        """Insert the event, or reconcile it if the id is already taken.

        `marker` is the subset of `extendedProperties.private` that proves
        this sync wrote the event. On a 409 the existing event is fetched:

        - cancelled (deleted by the owner) -> left deleted, never revived;
        - missing the marker -> someone else's event, never edited;
        - ours and `patch_body` is None -> append-only Activity, no write;
        - ours otherwise -> patched (Sleep, last sync wins).
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

        existing = events.get(calendarId=self.calendar_id, eventId=event_id).execute()
        if existing.get("status") == "cancelled":
            return SKIPPED_DELETED
        private = (existing.get("extendedProperties") or {}).get("private") or {}
        if any(private.get(key) != value for key, value in marker.items()):
            return SKIPPED_FOREIGN
        if patch_body is None:
            return UNCHANGED
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
    if not service_account_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is required")

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)
