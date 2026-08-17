"""Garmin Connect client adapter for the publication pipeline."""

import asyncio
import json
import tempfile
from pathlib import Path


class GarminPublicationClient:
    """Small async adapter over `python-garminconnect` for publication."""

    def __init__(
        self,
        tokenstore,
        is_only_running=True,
        is_cn=False,
        email=None,
        password=None,
    ):
        if not tokenstore:
            raise ValueError("GARMIN_TOKENS_JSON is required")

        from garminconnect import Garmin

        self._tokenstore_directory = None
        self._is_only_running = is_only_running
        # Passing email/password lets garminconnect's login() self-heal: it
        # tries the cached tokenstore first (no SSO hit), and only falls back
        # to a fresh credential login if the API rejects the cached token
        # (e.g. it expired or was revoked). Without credentials here, a
        # rejected token is a hard failure with no recovery.
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
            prefix="garmin-tokens-"
        )
        tokenstore_path = Path(self._tokenstore_directory.name)
        token_file = tokenstore_path / "garmin_tokens.json"
        token_file.write_text(
            json.dumps(token_json, separators=(",", ":")), encoding="utf-8"
        )
        token_file.chmod(0o600)
        return str(tokenstore_path)

    async def get_activities(self, start, limit):
        activity_type = "running" if self._is_only_running else None
        return await asyncio.to_thread(
            self._client.get_activities,
            start=start,
            limit=limit,
            activitytype=activity_type,
        )

    async def download_activity(self, activity_id, file_type="fit"):
        from garminconnect import Garmin

        if file_type != "fit":
            raise ValueError("Garmin Publication only supports FIT downloads")

        return await asyncio.to_thread(
            self._client.download_activity,
            activity_id,
            Garmin.ActivityDownloadFormat.ORIGINAL,
        )

    async def aclose(self):
        if self._tokenstore_directory:
            self._tokenstore_directory.cleanup()
        return None
