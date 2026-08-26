"""Garmin Connect reads for the Timeline Sync."""

import asyncio
import json
import tempfile
from pathlib import Path


class GarminTimelineClient:
    """Async adapter over `python-garminconnect` for Timeline reads.

    Deliberately separate from `GarminPublicationClient`: that class guards
    the archive-first publication invariant and admits Runs alone, where the
    Timeline admits every activity type plus Sleep. See ADR 0007.
    """

    def __init__(self, tokenstore, is_cn=False, email=None, password=None):
        if not tokenstore:
            raise ValueError("GARMIN_TOKENS_JSON is required")

        from garminconnect import Garmin

        self._tokenstore_directory = None
        # Passing email/password lets garminconnect's login() self-heal: it
        # tries the cached tokenstore first, and only falls back to a fresh
        # credential login if the API rejects the cached token.
        self._client = Garmin(email=email, password=password, is_cn=is_cn)
        mfa_status, _legacy_token = self._client.login(
            tokenstore=self._tokenstore_input(tokenstore)
        )
        if mfa_status:
            raise ValueError(
                "Garmin login requires MFA, which isn't supported in this "
                "headless pipeline. Regenerate GARMIN_TOKENS_JSON "
                "interactively with run_page/get_garmin_tokens.py and update "
                "the GitHub secret."
            )

    def _tokenstore_input(self, tokenstore):
        try:
            token_json = json.loads(tokenstore)
        except json.JSONDecodeError:
            return tokenstore

        self._tokenstore_directory = tempfile.TemporaryDirectory(
            prefix="garmin-timeline-tokens-"
        )
        tokenstore_path = Path(self._tokenstore_directory.name)
        token_file = tokenstore_path / "garmin_tokens.json"
        token_file.write_text(
            json.dumps(token_json, separators=(",", ":")), encoding="utf-8"
        )
        token_file.chmod(0o600)
        return str(tokenstore_path)

    async def get_activities(self, start=0, limit=100):
        """Every activity type, not Runs alone — activitytype is omitted."""
        return await asyncio.to_thread(
            self._client.get_activities, start=start, limit=limit
        )

    async def get_sleep(self, cdate):
        """One day of sleep. `cdate` is an ISO date string."""
        return await asyncio.to_thread(self._client.get_sleep_data, cdate)

    async def aclose(self):
        if self._tokenstore_directory:
            self._tokenstore_directory.cleanup()
        return None
