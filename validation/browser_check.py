"""Explicit real-browser acceptance check; never replaced with a mock or silent skip."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from elyon.desktop import run_fixture_validation, run_validation


class DesktopAcceptance(unittest.TestCase):
    def test_real_cache_sw_policy_and_nested_fixture_coverage(self):
        with tempfile.TemporaryDirectory() as root:
            result = asyncio.run(run_fixture_validation(Path(root)))
            self.assertTrue(result["cacheAndRevalidationStimuliCompleted"])
            self.assertTrue(result["serviceWorkerHandlingObserved"])
            self.assertTrue(result["policyFixtureBlockedFetch"])
            self.assertTrue(result["nestedWorkerFixtureCompleted"])
            self.assertTrue(result["unknownChildTargetsPreserved"])
            self.assertFalse(result["wire304OrCacheOriginVerified"])
            self.assertTrue(result["lateResponseDidNotAcquireNewGeneration"])
            self.assertTrue(result["failedRequestReferencesValid"])

    def test_real_response_redirect_stall_and_termination_100_runs(self):
        with tempfile.TemporaryDirectory() as root:
            result = asyncio.run(run_validation(Path(root), runs=100))
            self.assertEqual(result["verifiedRedirectRuns"], 100)
            self.assertGreaterEqual(result["stallSeconds"], 5)
            self.assertGreater(result["controlsDuringStall"], 0)
            self.assertTrue(result["deliveredEvidencePreservedAfterCrash"])
            self.assertEqual(result["retainedAdapterObjects"], 0)
            self.assertFalse(result["nativeUIVerified"])
            self.assertEqual(result["source"], "desktop-chromium-playwright")
            exported = json.loads((Path(root) / "evidence.json").read_text())
            self.assertTrue(exported["manifest"]["redacted"])


if __name__ == "__main__":
    unittest.main()
