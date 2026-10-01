import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import branding


class BrandingTests(unittest.IsolatedAsyncioTestCase):
    def test_mascot_asset_is_a_png_with_stable_fingerprint(self) -> None:
        avatar = branding.brand_avatar_bytes()

        self.assertTrue(avatar.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(len(branding.brand_avatar_fingerprint()), 16)

    async def test_bot_avatar_only_uploads_once_per_asset_revision(self) -> None:
        user = type("FakeUser", (), {"edit": AsyncMock()})()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "brand-avatar.sha256"
            with patch.object(branding, "BRAND_STATE_PATH", state_path):
                self.assertTrue(await branding.sync_bot_avatar(user))
                self.assertFalse(await branding.sync_bot_avatar(user))

        user.edit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
