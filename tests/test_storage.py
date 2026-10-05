import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from tokapp_collector.storage import JsonStore


class JsonStoreTests(unittest.TestCase):
    def test_new_data_directories_and_files_are_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            previous_umask = os.umask(0o022)
            try:
                store = JsonStore(Path(tmp) / "data")
                store.save_message("1", {"text": "private fixture"})
            finally:
                os.umask(previous_umask)
            for directory in (store.root, store.messages_dir, store.events_dir, store.state_dir):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(store.message_path("1").stat().st_mode), 0o600)

    def test_each_source_message_is_a_separate_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonStore(Path(tmp))
            store.save_message("123", {"id": 123, "status": "stored"})
            store.save_message("456", {"id": 456, "status": "stored"})

            files = sorted((Path(tmp) / "messages").glob("*.json"))
            self.assertEqual([file.name for file in files], ["123.json", "456.json"])
            self.assertEqual(json.loads(files[0].read_text())["id"], 123)

    def test_finds_recent_event_by_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonStore(Path(tmp))
            store.save_event("evt-1", {
                "event_id": "evt-1",
                "fingerprint": "abc",
                "last_seen_at": "2026-09-04T10:00:00+00:00",
            })

            found = store.find_recent_event(
                "abc", now="2026-09-05T09:00:00+00:00", window_hours=48
            )
            self.assertEqual(found["event_id"], "evt-1")


if __name__ == "__main__":
    unittest.main()
