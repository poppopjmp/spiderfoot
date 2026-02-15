"""Tests for spiderfoot.module_versioning."""
from __future__ import annotations

import pytest
from spiderfoot.plugins.module_versioning import (
    VersionBump,
    SemanticVersion,
    VersionConstraint,
    ChangelogEntry,
    ModuleVersionInfo,
    ModuleVersionRegistry,
)


class TestSemanticVersion:
    def test_defaults(self):
        v = SemanticVersion()
        assert str(v) == "0.0.0"

    def test_str(self):
        v = SemanticVersion(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_parse(self):
        v = SemanticVersion.parse("2.5.1")
        assert v.major == 2
        assert v.minor == 5
        assert v.patch == 1

    def test_parse_invalid(self):
        with pytest.raises(ValueError):
            SemanticVersion.parse("invalid")

    def test_comparison(self):
        assert SemanticVersion(1, 0, 0) < SemanticVersion(2, 0, 0)
        assert SemanticVersion(1, 1, 0) > SemanticVersion(1, 0, 9)
        assert SemanticVersion(1, 0, 0) == SemanticVersion(1, 0, 0)

    def test_bump_major(self):
        v = SemanticVersion(1, 2, 3).bump(VersionBump.MAJOR)
        assert str(v) == "2.0.0"

    def test_bump_minor(self):
        v = SemanticVersion(1, 2, 3).bump(VersionBump.MINOR)
        assert str(v) == "1.3.0"

    def test_bump_patch(self):
        v = SemanticVersion(1, 2, 3).bump(VersionBump.PATCH)
        assert str(v) == "1.2.4"

    def test_compatible(self):
        v1 = SemanticVersion(1, 0, 0)
        v2 = SemanticVersion(1, 5, 0)
        v3 = SemanticVersion(2, 0, 0)
        assert v1.is_compatible_with(v2)
        assert not v1.is_compatible_with(v3)

    def test_to_dict(self):
        v = SemanticVersion(1, 2, 3)
        d = v.to_dict()
        assert d["string"] == "1.2.3"


class TestVersionConstraint:
    def test_gte(self):
        c = VersionConstraint.parse(">=1.0.0")
        assert c.check(SemanticVersion(1, 0, 0))
        assert c.check(SemanticVersion(2, 0, 0))
        assert not c.check(SemanticVersion(0, 9, 0))

    def test_lt(self):
        c = VersionConstraint.parse("<2.0.0")
        assert c.check(SemanticVersion(1, 9, 9))
        assert not c.check(SemanticVersion(2, 0, 0))

    def test_eq(self):
        c = VersionConstraint.parse("==1.5.0")
        assert c.check(SemanticVersion(1, 5, 0))
        assert not c.check(SemanticVersion(1, 5, 1))

    def test_neq(self):
        c = VersionConstraint.parse("!=1.0.0")
        assert c.check(SemanticVersion(1, 0, 1))
        assert not c.check(SemanticVersion(1, 0, 0))

    def test_caret(self):
        c = VersionConstraint.parse("^1.2.0")
        assert c.check(SemanticVersion(1, 3, 0))
        assert not c.check(SemanticVersion(2, 0, 0))
        assert not c.check(SemanticVersion(1, 1, 0))

    def test_tilde(self):
        c = VersionConstraint.parse("~1.2.0")
        assert c.check(SemanticVersion(1, 2, 5))
        assert not c.check(SemanticVersion(1, 3, 0))

    def test_parse_invalid(self):
        with pytest.raises(ValueError):
            VersionConstraint.parse("bad")

    def test_str(self):
        c = VersionConstraint.parse(">=1.0.0")
        assert str(c) == ">=1.0.0"


class TestChangelogEntry:
    def test_to_dict(self):
        e = ChangelogEntry(
            version=SemanticVersion(1, 0, 0),
            description="Initial release",
            author="dev",
        )
        d = e.to_dict()
        assert d["version"] == "1.0.0"
        assert d["description"] == "Initial release"


class TestModuleVersionInfo:
    def test_defaults(self):
        info = ModuleVersionInfo("sfp_dns")
        assert str(info.current_version) == "1.0.0"
        assert not info.is_deprecated

    def test_bump(self):
        info = ModuleVersionInfo("sfp_dns")
        info.bump(VersionBump.MINOR, "Added feature X")
        assert str(info.current_version) == "1.1.0"
        assert len(info.changelog) == 1
        assert info.changelog[0].description == "Added feature X"

    def test_bump_chaining(self):
        info = ModuleVersionInfo("sfp_dns")
        result = info.bump(VersionBump.PATCH, "fix")
        assert result is info

    def test_major_bump_breaking(self):
        info = ModuleVersionInfo("sfp_dns")
        info.bump(VersionBump.MAJOR, "Breaking change")
        assert info.changelog[0].breaking is True

    def test_dependency(self):
        info = ModuleVersionInfo("sfp_dns")
        info.add_dependency("sfp_resolver", ">=1.0.0")
        assert info.check_dependency("sfp_resolver", SemanticVersion(1, 5, 0))
        assert not info.check_dependency("sfp_resolver", SemanticVersion(0, 9, 0))

    def test_dependency_chaining(self):
        info = ModuleVersionInfo("sfp_dns")
        result = info.add_dependency("sfp_x", ">=1.0.0")
        assert result is info

    def test_remove_dependency(self):
        info = ModuleVersionInfo("sfp_dns")
        info.add_dependency("sfp_x", ">=1.0.0")
        assert info.remove_dependency("sfp_x") is True
        assert info.remove_dependency("sfp_x") is False

    def test_no_constraint_compatible(self):
        info = ModuleVersionInfo("sfp_dns")
        assert info.check_dependency("unknown", SemanticVersion(5, 0, 0))

    def test_deprecate(self):
        info = ModuleVersionInfo("sfp_old")
        info.deprecate("Use sfp_new instead")
        assert info.is_deprecated
        d = info.to_dict()
        assert d["deprecated"] is True
        assert "sfp_new" in d["deprecation_message"]

    def test_to_dict(self):
        info = ModuleVersionInfo("sfp_dns", SemanticVersion(2, 1, 0))
        d = info.to_dict()
        assert d["module_name"] == "sfp_dns"
        assert d["current_version"] == "2.1.0"


class TestModuleVersionRegistry:
    def test_register(self):
        reg = ModuleVersionRegistry()
        info = reg.register("sfp_dns", "1.0.0")
        assert str(info.current_version) == "1.0.0"

    def test_register_default_version(self):
        reg = ModuleVersionRegistry()
        info = reg.register("sfp_dns")
        assert str(info.current_version) == "1.0.0"

    def test_get(self):
        reg = ModuleVersionRegistry()
        reg.register("sfp_dns")
        assert reg.get("sfp_dns") is not None
        assert reg.get("missing") is None

    def test_unregister(self):
        reg = ModuleVersionRegistry()
        reg.register("sfp_dns")
        assert reg.unregister("sfp_dns") is True
        assert reg.unregister("sfp_dns") is False

    def test_list_modules(self):
        reg = ModuleVersionRegistry()
        reg.register("sfp_b")
        reg.register("sfp_a")
        assert reg.list_modules() == ["sfp_a", "sfp_b"]

    def test_get_deprecated(self):
        reg = ModuleVersionRegistry()
        reg.register("sfp_old").deprecate()
        reg.register("sfp_new")
        assert reg.get_deprecated() == ["sfp_old"]

    def test_check_compatibility(self):
        reg = ModuleVersionRegistry()
        info = reg.register("sfp_dns")
        info.add_dependency("sfp_resolver", ">=1.0.0")
        assert reg.check_compatibility("sfp_dns", "sfp_resolver", "1.5.0")
        assert not reg.check_compatibility("sfp_dns", "sfp_resolver", "0.5.0")

    def test_find_dependents(self):
        reg = ModuleVersionRegistry()
        reg.register("sfp_dns").add_dependency("sfp_resolver", ">=1.0.0")
        reg.register("sfp_resolver")
        assert reg.find_dependents("sfp_resolver") == ["sfp_dns"]

    def test_summary(self):
        reg = ModuleVersionRegistry()
        reg.register("sfp_a", "1.0.0")
        reg.register("sfp_b", "2.0.0")
        s = reg.summary()
        assert s["total_modules"] == 2
        assert s["modules"]["sfp_a"] == "1.0.0"

    def test_to_dict(self):
        reg = ModuleVersionRegistry()
        reg.register("sfp_a")
        d = reg.to_dict()
        assert "modules" in d
        assert "summary" in d
