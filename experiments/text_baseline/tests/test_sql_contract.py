from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20260911000000_pilot_text_baseline.sql"
CONFIG = ROOT / "supabase" / "config.toml"


class SqlContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = MIGRATION.read_text(encoding="utf-8")
        self.config = CONFIG.read_text(encoding="utf-8")

    def test_invoker_search_path_and_rls(self) -> None:
        self.assertGreaterEqual(self.sql.count("security invoker"), 5)
        self.assertGreaterEqual(self.sql.count("set search_path = ''"), 5)
        self.assertIn("enable row level security", self.sql)
        self.assertNotIn("security definer", self.sql.lower().replace("security invoker", ""))
        self.assertNotIn("service_role", self.sql)

    def test_ownership_and_retrieval_are_separate(self) -> None:
        self.assertIn("verify_pilot_snapshot_ownership", self.sql)
        self.assertIn("retrieve_pilot_memory", self.sql)
        self.assertIn("extensions.vector(384)", self.sql)
        self.assertIn("item_kind in ('fact', 'source_passage')", self.sql)
        self.assertIn("s.owner_id = (select auth.uid())", self.sql)
        self.assertIn("public.pilot_supervised()", self.sql)
        self.assertIn("status = 'pending'", self.sql)
        self.assertIn("pilot_recent_call_count", self.sql)

    def test_jwt_remains_required(self) -> None:
        self.assertIn("verify_jwt = true", self.config)
        self.assertIn("text-baseline-pilot", self.config)


if __name__ == "__main__":
    unittest.main()
