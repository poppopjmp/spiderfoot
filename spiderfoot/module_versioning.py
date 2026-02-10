"""Module versioning system for SpiderFoot.

Tracks module versions, compatibility, changelogs, and migration paths.
Supports semantic versioning with comparison and constraint checking.
"""

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class VersionBump(Enum):
    """Type of version increment."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass(frozen=True, order=True)
class SemanticVersion:
    """Semantic version (major.minor.patch).

    Supports comparison operators via ordering.
    """
    major: int = 0
    minor: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, bump_type: VersionBump) -> "SemanticVersion":
        """Return a new version with the specified component bumped."""
        if bump_type == VersionBump.MAJOR:
            return SemanticVersion(self.major + 1, 0, 0)
        elif bump_type == VersionBump.MINOR:
            return SemanticVersion(self.major, self.minor + 1, 0)
        elif bump_type == VersionBump.PATCH:
            return SemanticVersion(self.major, self.minor, self.patch + 1)
        return self

    def is_compatible_with(self, other: "SemanticVersion") -> bool:
        """Check if this version is compatible with another (same major)."""
        return self.major == other.major

    @staticmethod
    def parse(version_str: str) -> "SemanticVersion":
        """Parse a version string like '1.2.3'."""
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str.strip())
        if not match:
            raise ValueError(f"Invalid version string: {version_str}")
        return SemanticVersion(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    def to_dict(self) -> dict:
        return {"major": self.major, "minor": self.minor, "patch": self.patch, "string": str(self)}


@dataclass
class VersionConstraint:
    """A version constraint like '>=1.0.0', '<2.0.0'."""
    operator: str  # '>=', '<=', '==', '!=', '>', '<', '^', '~'
    version: SemanticVersion

    def check(self, candidate: SemanticVersion) -> bool:
        """Check if a candidate version satisfies this constraint."""
        if self.operator == ">=":
            return candidate >= self.version
        elif self.operator == "<=":
            return candidate <= self.version
        elif self.operator == "==":
            return candidate == self.version
        elif self.operator == "!=":
            return candidate != self.version
        elif self.operator == ">":
            return candidate > self.version
        elif self.operator == "<":
            return candidate < self.version
        elif self.operator == "^":
            # Compatible with (same major, >= version)
            return candidate.major == self.version.major and candidate >= self.version
        elif self.operator == "~":
            # Approximately (same major.minor, >= version)
            return (candidate.major == self.version.major
                    and candidate.minor == self.version.minor
                    and candidate >= self.version)
        return False

    def __str__(self) -> str:
        return f"{self.operator}{self.version}"

    @staticmethod
    def parse(constraint_str: str) -> "VersionConstraint":
        """Parse a constraint string like '>=1.0.0'."""
        match = re.match(r"^([>=<!^~]+)(\d+\.\d+\.\d+)$", constraint_str.strip())
        if not match:
            raise ValueError(f"Invalid constraint: {constraint_str}")
        return VersionConstraint(
            operator=match.group(1),
            version=SemanticVersion.parse(match.group(2)),
        )


@dataclass
class ChangelogEntry:
    """A single changelog entry for a version."""
    version: SemanticVersion
    description: str
    author: str = ""
    timestamp: float = field(default_factory=time.time)
    breaking: bool = False

    def to_dict(self) -> dict:
        return {
            "version": str(self.version),
            "description": self.description,
            "author": self.author,
            "timestamp": self.timestamp,
            "breaking": self.breaking,
        }


class ModuleVersionInfo:
    """Version tracking for a single module.

    Args:
        module_name: Module identifier.
        current_version: Current semantic version.
    """

    def __init__(self, module_name: str, current_version: Optional[SemanticVersion] = None) -> None:
        self.module_name = module_name
        self.current_version = current_version or SemanticVersion(1, 0, 0)
        self._changelog: list[ChangelogEntry] = []
        self._dependencies: dict[str, VersionConstraint] = {}
        self._deprecated = False
        self._deprecation_message = ""

    def bump(self, bump_type: VersionBump, description: str = "", author: str = "") -> "ModuleVersionInfo":
        """Bump the version and add a changelog entry."""
        new_version = self.current_version.bump(bump_type)
        entry = ChangelogEntry(
            version=new_version,
            description=description or f"{bump_type.value} version bump",
            author=author,
            breaking=bump_type == VersionBump.MAJOR,
        )
        self._changelog.append(entry)
        self.current_version = new_version
        return self

    def add_dependency(self, module_name: str, constraint: str) -> "ModuleVersionInfo":
        """Add a versioned dependency on another module."""
        self._dependencies[module_name] = VersionConstraint.parse(constraint)
        return self

    def remove_dependency(self, module_name: str) -> bool:
        return self._dependencies.pop(module_name, None) is not None

    def check_dependency(self, module_name: str, version: SemanticVersion) -> bool:
        """Check if a dependency version satisfies the constraint."""
        constraint = self._dependencies.get(module_name)
        if constraint is None:
            return True  # No constraint = compatible
        return constraint.check(version)

    def deprecate(self, message: str = "") -> "ModuleVersionInfo":
        self._deprecated = True
        self._deprecation_message = message or f"{self.module_name} is deprecated"
        return self

    @property
    def is_deprecated(self) -> bool:
        return self._deprecated

    @property
    def changelog(self) -> list[ChangelogEntry]:
        return list(self._changelog)

    @property
    def dependencies(self) -> dict[str, VersionConstraint]:
        return dict(self._dependencies)

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "current_version": str(self.current_version),
            "deprecated": self._deprecated,
            "deprecation_message": self._deprecation_message if self._deprecated else None,
            "dependencies": {k: str(v) for k, v in self._dependencies.items()},
            "changelog": [e.to_dict() for e in self._changelog],
        }


class ModuleVersionRegistry:
    """Registry for tracking versions of all modules.

    Args:
        load_defaults: If True, starts empty (modules register themselves).
    """

    def __init__(self) -> None:
        self._modules: dict[str, ModuleVersionInfo] = {}

    def register(self, module_name: str, version: Optional[str] = None) -> ModuleVersionInfo:
        """Register a module with an optional initial version."""
        sv = SemanticVersion.parse(version) if version else SemanticVersion(1, 0, 0)
        info = ModuleVersionInfo(module_name, sv)
        self._modules[module_name] = info
        return info

    def get(self, module_name: str) -> Optional[ModuleVersionInfo]:
        return self._modules.get(module_name)

    def unregister(self, module_name: str) -> bool:
        return self._modules.pop(module_name, None) is not None

    def list_modules(self) -> list[str]:
        return sorted(self._modules.keys())

    def get_deprecated(self) -> list[str]:
        return [name for name, info in self._modules.items() if info.is_deprecated]

    def check_compatibility(self, module_name: str, dep_name: str, dep_version: str) -> bool:
        """Check if a dependency version is compatible with a module's constraint."""
        info = self._modules.get(module_name)
        if info is None:
            return True
        return info.check_dependency(dep_name, SemanticVersion.parse(dep_version))

    def find_dependents(self, module_name: str) -> list[str]:
        """Find all modules that depend on a given module."""
        return [
            name for name, info in self._modules.items()
            if module_name in info.dependencies
        ]

    def summary(self) -> dict:
        return {
            "total_modules": len(self._modules),
            "deprecated": len(self.get_deprecated()),
            "modules": {name: str(info.current_version) for name, info in sorted(self._modules.items())},
        }

    def to_dict(self) -> dict:
        return {
            "modules": {name: info.to_dict() for name, info in self._modules.items()},
            "summary": self.summary(),
        }
