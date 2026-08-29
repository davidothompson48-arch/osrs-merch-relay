import unittest

import update_opportunity_book as book


def config():
    return {
        "phase3": {
            "persistent_opportunity_book": {
                "maximum_consecutive_gap_seconds": 720,
                "retention_hours": 168,
                "maximum_records": 50,
                "minimum_cycles_before_review": 2,
                "minimum_candidate_observations_before_review": 2,
            },
            "repeatability_multiplier": {
                "minimum_book_observations": 2,
                "minimum_consecutive_observations": 2,
                "minimum_qualified_ratio": 0.5,
            },
        }
    }


def packet(snapshot_unix):
    return {"generated_unix": snapshot_unix, "quality": {"core_age_seconds": 0}}


def row(hurdle_pass=True):
    return {
        "engine": "evergreen",
        "item_or_strategy": "Test item",
        "expected_profit_at_capacity_gp": 300_000,
        "expected_gp_per_hour": 10_000,
        "capacity_gp": 1_000_000,
        "expected_hold_hours": 72,
        "slot_bucket": "PARKING",
        "minimum_absolute_profit_hurdle_pass": hurdle_pass,
    }


class OpportunityBookTests(unittest.TestCase):
    def test_same_market_snapshot_is_deduplicated(self):
        state, updated = book.update_book({}, [row()], packet(1_000), config(), 1_000)
        state, updated_again = book.update_book(state, [row()], packet(1_000), config(), 1_001)

        record = state["records"]["evergreen::Test item"]
        self.assertTrue(updated)
        self.assertFalse(updated_again)
        self.assertEqual(state["cycles_observed"], 1)
        self.assertEqual(record["observations"], 1)

    def test_distinct_snapshots_build_repeatability_and_review_sample(self):
        state, _ = book.update_book({}, [row()], packet(1_000), config(), 1_000)
        state, _ = book.update_book(state, [row()], packet(1_300), config(), 1_300)
        summary = book.book_summary(state, config(), True)

        record = state["records"]["evergreen::Test item"]
        self.assertEqual(record["repeatability_class"], "REPEATABLE")
        self.assertEqual(record["consecutive_observations"], 2)
        self.assertEqual(record["qualified_ratio"], 1.0)
        self.assertTrue(summary["review_data_sufficient"])

    def test_missing_snapshot_resets_consecutive_chain(self):
        state, _ = book.update_book({}, [row()], packet(1_000), config(), 1_000)
        state, _ = book.update_book(state, [], packet(1_300), config(), 1_300)

        self.assertEqual(state["records"]["evergreen::Test item"]["consecutive_observations"], 0)
        self.assertEqual(state["records"]["evergreen::Test item"]["missed_snapshots"], 1)


if __name__ == "__main__":
    unittest.main()
