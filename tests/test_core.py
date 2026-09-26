import json
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from pathlib import Path

from app_constants import DATA_FILE
from auth_utils import hash_password, verify_password
from cloud_data_service import merge_training_data
from data_store import load_training_data, load_users, save_training_data, save_users
from training_utils import (
    get_current_training_streak,
    get_longest_training_streak,
    get_rank_for_xp,
    get_task_category,
    get_training_badges,
    get_training_chart_data,
)
from update_utils import fetch_latest_release


class AuthTests(unittest.TestCase):
    def test_pbkdf2_password_round_trip(self):
        stored_password = hash_password("TestHaslo123!")
        self.assertTrue(stored_password.startswith("pbkdf2_sha256$"))
        self.assertEqual(verify_password("TestHaslo123!", stored_password), (True, False))
        self.assertEqual(verify_password("wrong", stored_password), (False, False))

    def test_legacy_password_is_detected(self):
        self.assertEqual(verify_password("legacy", "legacy"), (True, True))


class TrainingUtilsTests(unittest.TestCase):
    def test_rank_and_category(self):
        self.assertEqual(get_rank_for_xp(0), "Silver I")
        self.assertEqual(get_rank_for_xp(120), "Silver II")
        self.assertEqual(get_task_category({"type": "AWP Flicks"}), "AWP")
        self.assertEqual(get_task_category({"type": "AK47 Spray Control"}), "Recoil")

    def test_streaks_and_badges(self):
        today = date(2026, 9, 26)
        data = {
            "completion_history": [
                {"date": (today - timedelta(days=offset)).isoformat()}
                for offset in range(7)
            ]
        }
        self.assertEqual(get_current_training_streak(data, today), 7)
        self.assertEqual(get_longest_training_streak(data), 7)
        self.assertIn("🏅 7 dni regularności", get_training_badges(data))

    def test_chart_data_has_expected_period_lengths(self):
        data = {"completion_history": [{"date": "2026-09-26", "duration_seconds": 60}]}
        week = get_training_chart_data(data, "week", date(2026, 9, 26))
        month = get_training_chart_data(data, "month", date(2026, 9, 26))
        self.assertEqual([len(values) for values in week], [7, 7, 7])
        self.assertEqual([len(values) for values in month], [30, 30, 30])


class UpdateUtilsTests(unittest.TestCase):
    def test_new_release_without_installer_is_reported_as_pending(self):
        release_data = {"tag_name": "v1.0.5", "assets": [], "body": ""}
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(release_data).encode("utf-8")

        with patch("update_utils.urllib.request.urlopen", return_value=response):
            release = fetch_latest_release("1.0.4")

        self.assertEqual(release["version"], "v1.0.5")
        self.assertFalse(release["installer_ready"])
        self.assertEqual(release["url"], "")

    def test_release_with_installer_is_ready(self):
        release_data = {
            "tag_name": "v1.0.5",
            "assets": [{"name": "CS2Trening-Setup.exe", "browser_download_url": "https://example.test/setup.exe"}],
            "body": "",
        }
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(release_data).encode("utf-8")

        with patch("update_utils.urllib.request.urlopen", return_value=response):
            release = fetch_latest_release("1.0.4")

        self.assertTrue(release["installer_ready"])
        self.assertEqual(release["url"], "https://example.test/setup.exe")


class DataStoreTests(unittest.TestCase):
    def test_training_data_merge_keeps_both_device_histories(self):
        merged = merge_training_data(
            {"completed_count": 1, "total_seconds_spent": 10, "completion_history": [{"date": "2026-09-26", "duration_seconds": 10, "duration": 1}]},
            {"completed_count": 1, "total_seconds_spent": 20, "completion_history": [{"date": "2026-09-27", "duration_seconds": 20, "duration": 1}]}
        )
        self.assertEqual(len(merged["completion_history"]), 2)
        self.assertEqual(merged["completed_count"], 2)
        self.assertEqual(merged["total_seconds_spent"], 30)

    def test_users_and_training_data_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            users_path = root / "users.json"
            training_path = root / "training.json"
            users = {"admin": {"password": hash_password("secret")}}
            training = {"users": {"admin": {"completed_count": 2}}}
            save_users(users_path, users)
            save_training_data(training_path, training)
            self.assertIn("admin", load_users(users_path, hash_password))
            self.assertEqual(load_training_data(training_path)["users"]["admin"]["completed_count"], 2)

    def test_training_data_adds_default_shared_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "training.json"
            path.write_text(json.dumps({"users": {}}), encoding="utf-8")
            loaded = load_training_data(path)
            self.assertTrue(loaded["module_catalog"])
            self.assertTrue(loaded["preset_protocols"])


if __name__ == "__main__":
    unittest.main()
