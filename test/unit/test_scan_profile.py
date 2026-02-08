#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for spiderfoot.scan_profile."""

import json
import os
import tempfile
import unittest

from spiderfoot.scan_profile import (
    ProfileCategory,
    ProfileManager,
    ScanProfile,
    get_profile_manager,
)


# Mock modules for testing
MOCK_MODULES = {
    "sfp_dns": {
        "meta": {
            "name": "DNS Resolver",
            "flags": [],
            "useCases": ["Footprint", "Investigate", "Passive"],
            "categories": ["DNS"],
        },
        "producedEvents": ["IP_ADDRESS", "INTERNET_NAME"],
    },
    "sfp_shodan": {
        "meta": {
            "name": "Shodan",
            "flags": ["apikey"],
            "useCases": ["Footprint", "Investigate"],
            "categories": ["Crawling and Scanning"],
        },
        "producedEvents": ["TCP_PORT_OPEN", "VULNERABILITY_CVE_HIGH"],
    },
    "sfp_spider": {
        "meta": {
            "name": "Web Spider",
            "flags": ["slow"],
            "useCases": ["Footprint"],
            "categories": ["Crawling and Scanning"],
        },
        "producedEvents": ["LINKED_URL_INTERNAL", "TARGET_WEB_CONTENT"],
    },
    "sfp_torch": {
        "meta": {
            "name": "Torch",
            "flags": ["tor", "errorprone"],
            "useCases": ["Investigate"],
            "categories": ["Secondary Networks"],
        },
        "producedEvents": ["DARKNET_MENTION_URL"],
    },
    "sfp_twitter": {
        "meta": {
            "name": "Twitter",
            "flags": ["apikey"],
            "useCases": ["Footprint", "Investigate"],
            "categories": ["Social Media"],
        },
        "producedEvents": ["SOCIAL_MEDIA"],
    },
    "sfp_nmap": {
        "meta": {
            "name": "Nmap",
            "flags": ["tool", "invasive"],
            "useCases": ["Footprint"],
            "categories": ["Crawling and Scanning"],
        },
        "producedEvents": ["TCP_PORT_OPEN"],
    },
    "sfp__stor_db": {
        "meta": {
            "name": "Storage",
            "flags": [],
            "useCases": [],
            "categories": [],
        },
        "producedEvents": [],
    },
}


class TestScanProfile(unittest.TestCase):
    """Test ScanProfile."""

    def test_defaults(self):
        p = ScanProfile(name="test", display_name="Test")
        self.assertEqual(p.name, "test")
        self.assertEqual(p.use_cases, [])
        self.assertEqual(p.max_threads, 0)

    def test_resolve_modules_by_usecase(self):
        p = ScanProfile(
            name="test", display_name="Test",
            use_cases=["Passive"])
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertIn("sfp_dns", modules)
        self.assertNotIn("sfp_nmap", modules)  # Not Passive

    def test_resolve_modules_exclude_flags(self):
        p = ScanProfile(
            name="test", display_name="Test",
            use_cases=["Passive"],
            exclude_flags=["apikey"])
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertIn("sfp_dns", modules)
        # sfp_twitter has apikey flag
        self.assertNotIn("sfp_twitter", modules)

    def test_resolve_modules_include_specific(self):
        p = ScanProfile(
            name="test", display_name="Test",
            include_modules=["sfp_dns", "sfp_spider"])
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertIn("sfp_dns", modules)
        self.assertIn("sfp_spider", modules)

    def test_resolve_modules_exclude_specific(self):
        p = ScanProfile(
            name="test", display_name="Test",
            use_cases=["Passive"],
            exclude_modules=["sfp_dns"])
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertNotIn("sfp_dns", modules)

    def test_resolve_modules_always_includes_storage(self):
        p = ScanProfile(
            name="test", display_name="Test",
            include_modules=["sfp_dns"])
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertIn("sfp__stor_db", modules)

    def test_resolve_modules_include_categories(self):
        p = ScanProfile(
            name="test", display_name="Test",
            include_categories=["Social Media"])
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertIn("sfp_twitter", modules)
        self.assertNotIn("sfp_dns", modules)

    def test_apply_overrides(self):
        p = ScanProfile(
            name="test", display_name="Test",
            option_overrides={"_debug": True},
            max_threads=10)
        opts = p.apply_overrides({"_debug": False, "_maxthreads": 3})
        self.assertTrue(opts["_debug"])
        self.assertEqual(opts["_maxthreads"], 10)

    def test_apply_overrides_no_mutate(self):
        p = ScanProfile(
            name="test", display_name="Test",
            option_overrides={"_debug": True})
        original = {"_debug": False}
        p.apply_overrides(original)
        self.assertFalse(original["_debug"])

    def test_to_dict(self):
        p = ScanProfile(
            name="test", display_name="Test Profile",
            use_cases=["Passive"], tags=["quick"])
        d = p.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["use_cases"], ["Passive"])
        self.assertIn("quick", d["tags"])

    def test_from_dict(self):
        data = {
            "name": "custom",
            "display_name": "Custom Profile",
            "use_cases": ["Footprint"],
            "exclude_flags": ["slow"],
            "max_threads": 5,
        }
        p = ScanProfile.from_dict(data)
        self.assertEqual(p.name, "custom")
        self.assertEqual(p.use_cases, ["Footprint"])
        self.assertEqual(p.max_threads, 5)

    def test_roundtrip(self):
        original = ScanProfile(
            name="test", display_name="Test",
            use_cases=["Passive"],
            exclude_flags=["slow"],
            max_threads=4,
            tags=["my-tag"])
        restored = ScanProfile.from_dict(original.to_dict())
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.use_cases, original.use_cases)
        self.assertEqual(restored.max_threads, original.max_threads)


class TestProfileManager(unittest.TestCase):
    """Test ProfileManager."""

    def setUp(self):
        self.pm = ProfileManager()

    def test_builtin_profiles(self):
        names = self.pm.list_names()
        self.assertIn("quick-recon", names)
        self.assertIn("full-footprint", names)
        self.assertIn("passive-only", names)
        self.assertIn("vuln-assessment", names)
        self.assertIn("social-media", names)
        self.assertIn("dark-web", names)
        self.assertIn("infrastructure", names)
        self.assertIn("api-powered", names)
        self.assertIn("minimal", names)
        self.assertIn("investigate", names)

    def test_get_profile(self):
        p = self.pm.get("quick-recon")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "quick-recon")

    def test_get_unknown(self):
        self.assertIsNone(self.pm.get("nonexistent"))

    def test_register_custom(self):
        p = ScanProfile(name="my-custom", display_name="Custom")
        self.pm.register(p)
        self.assertIsNotNone(self.pm.get("my-custom"))

    def test_delete(self):
        self.assertTrue(self.pm.delete("quick-recon"))
        self.assertIsNone(self.pm.get("quick-recon"))
        self.assertFalse(self.pm.delete("nonexistent"))

    def test_list_by_category(self):
        vuln = self.pm.list_profiles(ProfileCategory.VULNERABILITY)
        self.assertTrue(any(p.name == "vuln-assessment" for p in vuln))

    def test_quick_recon_excludes_invasive(self):
        p = self.pm.get("quick-recon")
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertNotIn("sfp_nmap", modules)       # tool
        self.assertNotIn("sfp_shodan", modules)      # apikey
        self.assertNotIn("sfp_torch", modules)       # tor

    def test_dark_web_includes_tor(self):
        p = self.pm.get("dark-web")
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertIn("sfp_torch", modules)

    def test_api_powered_requires_apikey(self):
        p = self.pm.get("api-powered")
        modules = p.resolve_modules(MOCK_MODULES)
        self.assertIn("sfp_shodan", modules)
        self.assertIn("sfp_twitter", modules)
        self.assertNotIn("sfp_dns", modules)  # No apikey flag

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            self.pm.register(ScanProfile(
                name="saveme", display_name="Save Me",
                tags=["test"]))

            self.assertTrue(self.pm.save_to_file("saveme", path))
            self.assertTrue(os.path.exists(path))

            # Load into fresh manager
            pm2 = ProfileManager()
            loaded = pm2.load_from_file(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.name, "saveme")

    def test_load_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save two profiles
            for name in ["p1", "p2"]:
                p = ScanProfile(name=name, display_name=name.upper())
                path = os.path.join(tmpdir, f"{name}.json")
                with open(path, "w") as f:
                    json.dump(p.to_dict(), f)

            pm2 = ProfileManager()
            count = pm2.load_directory(tmpdir)
            self.assertEqual(count, 2)

    def test_export_all(self):
        exported = self.pm.export_all()
        self.assertTrue(len(exported) >= 10)
        self.assertTrue(all("name" in p for p in exported))

    def test_singleton_convenience(self):
        pm = get_profile_manager()
        self.assertIsInstance(pm, ProfileManager)
        self.assertIsNotNone(pm.get("quick-recon"))


if __name__ == "__main__":
    unittest.main()
