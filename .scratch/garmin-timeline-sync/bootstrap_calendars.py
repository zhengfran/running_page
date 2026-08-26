"""One-off provisioning and verification for the Garmin Timeline Sync.

Throwaway. Not pipeline code — this runs once, by hand, to create the two
Timeline Calendars and to answer the three questions Google's documentation
leaves open (see ticket 009).

    pip install google-auth google-api-python-client

    python bootstrap_calendars.py provision ~/timeline-sync-key.json
    python bootstrap_calendars.py verify    ~/timeline-sync-key.json <workouts-calendar-id>
"""

import sys
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SHARE_WITH = "zhicheng.ink98@gmail.com"
TIME_ZONE = "Asia/Singapore"
CALENDARS = ["Workouts", "Sleep"]


def service(key_path):
    credentials = service_account.Credentials.from_service_account_file(
        key_path, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def provision(key_path):
    api = service(key_path)

    existing = {}
    for entry in api.calendarList().list().execute().get("items", []):
        existing[entry.get("summary")] = entry["id"]

    for name in CALENDARS:
        if name in existing:
            print(f"{name}: already exists, reusing {existing[name]}")
            calendar_id = existing[name]
        else:
            created = (
                api.calendars()
                .insert(body={"summary": name, "timeZone": TIME_ZONE})
                .execute()
            )
            calendar_id = created["id"]
            print(f"{name}: created {calendar_id}")

        rule = (
            api.acl()
            .insert(
                calendarId=calendar_id,
                body={
                    "role": "owner",
                    "scope": {"type": "user", "value": SHARE_WITH},
                },
            )
            .execute()
        )
        print(f"{name}: shared to {SHARE_WITH} as {rule['role']}")

    print("\nSecrets to set on zhengfran/running_page:")
    for name in CALENDARS:
        key = "GCAL_WORKOUTS_CALENDAR_ID" if name == "Workouts" else "GCAL_SLEEP_CALENDAR_ID"
        print(f"  {key}")
    print("  GOOGLE_SERVICE_ACCOUNT_JSON  (full contents of the key file)")
    print("\nNow check your inbox and click both invitation links once.")


def verify(key_path, calendar_id):
    """Answers live checks 2 and 3 from ticket 009."""
    api = service(key_path)
    event_id = "p" + str(int(time.time()))[-9:]  # base32hex: a-v and 0-9 only
    body = {
        "summary": "Timeline Sync probe",
        "start": {"dateTime": "2026-01-01T10:00:00Z"},
        "end": {"dateTime": "2026-01-01T11:00:00Z"},
    }

    print(f"probe id: {event_id}\n")

    api.events().insert(
        calendarId=calendar_id, body={**body, "id": event_id}, sendUpdates="none"
    ).execute()
    print("1. insert                        -> ok")

    try:
        api.events().insert(
            calendarId=calendar_id, body={**body, "id": event_id}, sendUpdates="none"
        ).execute()
        print("2. re-insert live event          -> NO 409 (unexpected)")
    except HttpError as error:
        print(f"2. re-insert live event          -> {error.resp.status} (409 expected)")

    before = api.events().get(calendarId=calendar_id, eventId=event_id).execute()
    patched = (
        api.events()
        .patch(
            calendarId=calendar_id,
            eventId=event_id,
            body={"status": "confirmed"},
            sendUpdates="none",
        )
        .execute()
    )
    moved = before.get("updated") != patched.get("updated")
    print(f"3. no-op patch on live event     -> ok, 'updated' changed: {moved}")

    api.events().delete(
        calendarId=calendar_id, eventId=event_id, sendUpdates="none"
    ).execute()
    print("4. delete                        -> ok")

    try:
        api.events().insert(
            calendarId=calendar_id, body={**body, "id": event_id}, sendUpdates="none"
        ).execute()
        print("5. re-insert deleted id          -> NO 409 (id was freed)")
    except HttpError as error:
        print(f"5. re-insert deleted id          -> {error.resp.status} (409 = tombstoned)")

    # THE LOAD-BEARING ONE. ADR 0006 rests on this working.
    try:
        revived = (
            api.events()
            .patch(
                calendarId=calendar_id,
                eventId=event_id,
                body={"status": "confirmed"},
                sendUpdates="none",
            )
            .execute()
        )
        print(f"6. REVIVE tombstone via patch    -> status={revived.get('status')}")
        print("   => ADR 0006 holds." if revived.get("status") == "confirmed"
              else "   => REVIVAL FAILED - ADR 0006 reopens.")
    except HttpError as error:
        print(f"6. REVIVE tombstone via patch    -> FAILED {error.resp.status}")
        print("   => ADR 0006 reopens: idempotency needs a state store.")

    try:
        api.events().delete(
            calendarId=calendar_id, eventId=event_id, sendUpdates="none"
        ).execute()
    except HttpError:
        pass
    print("\ncleaned up.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "provision":
        provision(sys.argv[2])
    elif sys.argv[1] == "verify":
        verify(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)
