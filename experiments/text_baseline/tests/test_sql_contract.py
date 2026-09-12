from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20260911000000_pilot_text_baseline.sql"
FK_INDEX_MIGRATION = ROOT / "supabase" / "migrations" / "20260912043729_add_pilot_fk_indexes.sql"
CONFIG = ROOT / "supabase" / "config.toml"

EXPECTED_FK_INDEXES = (
    (
        "pilot_memory_snapshots_owner_id_idx",
        "public.pilot_memory_snapshots",
        "owner_id",
    ),
    (
        "pilot_request_results_owner_id_idx",
        "public.pilot_request_results",
        "owner_id",
    ),
    (
        "pilot_request_results_snapshot_id_idx",
        "public.pilot_request_results",
        "snapshot_id",
    ),
)


class SqlContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = MIGRATION.read_text(encoding="utf-8")
        self.fk_sql = FK_INDEX_MIGRATION.read_text(encoding="utf-8")
        self.config = CONFIG.read_text(encoding="utf-8")

    def test_invoker_search_path_and_rls(self) -> None:
        self.assertGreaterEqual(self.sql.count("security invoker"), 5)
        self.assertGreaterEqual(self.sql.count("set search_path = ''"), 5)
        self.assertIn("enable row level security", self.sql)
        self.assertNotIn("service_role", self.sql)
        # Narrow write RPCs may be SECURITY DEFINER; every other function stays invoker.
        for name in ("claim_pilot_call", "insert_pilot_pending", "finalize_pilot_result"):
            self.assertIn(name, self.sql)
            self.assertRegex(
                self.sql,
                r"function public\.%s[\s\S]*?security definer[\s\S]*?set search_path = ''" % name,
            )
            self.assertIn("auth.uid()", self.sql.split(name, 1)[1][:1200])

    def test_ownership_and_retrieval_are_separate(self) -> None:
        self.assertIn("verify_pilot_snapshot_ownership", self.sql)
        self.assertIn("retrieve_pilot_memory", self.sql)
        self.assertIn("extensions.vector(384)", self.sql)
        self.assertIn("operator(extensions.<=>)", self.sql)
        self.assertIn("item_kind in ('fact', 'source_passage')", self.sql)
        self.assertIn("s.owner_id = (select auth.uid())", self.sql)
        self.assertIn("public.pilot_supervised()", self.sql)
        self.assertIn("status = 'pending'", self.sql)
        self.assertIn("pilot_recent_call_count", self.sql)
        self.assertIn("revoke all on table public.pilot_request_results", self.sql)
        self.assertIn("revoke all on table public.pilot_call_log", self.sql)
        self.assertNotIn("grant select, insert, update on table public.pilot_request_results", self.sql)
        self.assertNotIn("create policy pilot_results_insert_pending", self.sql)
        self.assertNotIn("create policy pilot_results_update_pending", self.sql)
        self.assertNotIn("create policy pilot_call_log_insert_own", self.sql)
        self.assertIn("snapshot not owned by caller", self.sql)
        self.assertIn("insert into public.pilot_call_log(user_id, request_id)", self.sql)

    def test_jwt_remains_required(self) -> None:
        self.assertIn("verify_jwt = true", self.config)
        self.assertIn("text-baseline-pilot", self.config)

    def test_fk_index_migration_is_index_only(self) -> None:
        cleaned = []
        for statement in self.fk_sql.split(";"):
            lines = [
                line
                for line in statement.splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            if lines:
                cleaned.append("\n".join(lines))
        self.assertEqual(len(cleaned), 3)

        found = []
        for statement in cleaned:
            match = re.search(
                r"create\s+index\s+(\w+)\s+on\s+(public\.\w+)\s*\((\w+)\)",
                statement,
                flags=re.IGNORECASE,
            )
            self.assertIsNotNone(match, msg="unexpected non-index statement: %s" % statement)
            assert match is not None
            found.append((match.group(1), match.group(2), match.group(3)))

        self.assertEqual(found, list(EXPECTED_FK_INDEXES))

        lowered = self.fk_sql.lower()
        forbidden = (
            "create policy",
            "alter policy",
            "drop policy",
            "enable row level security",
            "disable row level security",
            "grant ",
            "revoke ",
            "create or replace function",
            "create function",
            "alter function",
            "drop function",
            "alter table",
            "create table",
            "drop table",
        )
        for phrase in forbidden:
            self.assertNotIn(phrase, lowered)


if __name__ == "__main__":
    unittest.main()
