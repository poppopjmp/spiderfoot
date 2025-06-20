# Version Management

SpiderFoot uses a centralized version management system to ensure all version references across the repository are consistent and synchronized.

## Overview

All version information is controlled from a single source: the `VERSION` file in the repository root. This approach ensures:

- **Single Source of Truth**: The `VERSION` file is the canonical version reference
- **Automatic Synchronization**: All code modules automatically read from this file
- **Consistent Documentation**: All documentation uses the same version
- **Streamlined Releases**: Version updates are automated across all files

## Architecture

### Core Components

1. **`VERSION` File**: Contains the current version number (e.g., `5.2.1`)
2. **`spiderfoot/__version__.py`**: Python module that reads from the VERSION file
3. **`update_version.py`**: Utility script to update all version references
4. **`setup.py`**: Reads version directly from VERSION file for packaging

### Version Flow

```
VERSION file (5.2.1)
    ↓
spiderfoot/__version__.py → All Python modules
    ↓
update_version.py → Documentation, Docker files, CI/CD
```

## Usage

### Checking Current Version

```bash
# Display current version
python update_version.py --check

# List all managed files
python update_version.py --list
```

### Updating Version

```bash
# Set a new version and update all references
python update_version.py --set 5.3.0

# Update all references to match VERSION file
python update_version.py
```

### Version Validation

The utility automatically validates:
- Version format (X.Y.Z)
- Consistency across all files
- File existence and accessibility

## Managed Files

### Automatically Updated Files

These files are automatically updated by `update_version.py`:

- **`README.md`**: Badge versions and release links
- **`docs/index.rst`**: Documentation version headers
- **`docs/configuration.md`**: Version references in documentation
- **`docs/conf.py`**: Sphinx documentation configuration
- **`docker-compose-prod.yml`**: Production Docker image tags
- **`docker-compose.yml`**: Development Docker image tags
- **`.github/workflows/docker-image.yml`**: CI/CD Docker builds
- **`.github/workflows/acceptance_test.yml`**: Testing workflows
- **`spiderfoot/__version__.py`**: Fallback version for error cases

### Automatically Synchronized Files

These files automatically read from the VERSION file:

- **`setup.py`**: Python package version
- **All Python modules**: Import `__version__` from spiderfoot package
- **Web interface**: Displays version in UI
- **API responses**: Include version information
- **CLI tools**: Version information in help and headers

## Release Process

### Standard Release

1. **Update VERSION file**:
   ```bash
   python update_version.py --set 5.3.0
   ```

2. **Verify consistency**:
   ```bash
   python update_version.py --check
   ```

3. **Commit changes**:
   ```bash
   git add -A
   git commit -m "Release v5.3.0"
   git tag v5.3.0
   ```

4. **Push release**:
   ```bash
   git push origin main --tags
   ```

### Emergency Hotfix

For urgent fixes requiring version updates:

```bash
# Quick version bump
python update_version.py --set 5.2.2
git add -A && git commit -m "Hotfix v5.2.2" && git tag v5.2.2
git push origin main --tags
```

## Best Practices

### Version Numbering

SpiderFoot follows [Semantic Versioning](https://semver.org/):

- **Major (X.0.0)**: Breaking changes, major new features
- **Minor (X.Y.0)**: New features, backward compatible
- **Patch (X.Y.Z)**: Bug fixes, backward compatible

### Development Workflow

1. **Never manually edit version numbers** in individual files
2. **Always use `update_version.py`** for version changes
3. **Run `--check` before releases** to verify consistency
4. **Test after version updates** to ensure all systems work
5. **Document version changes** in release notes

### CI/CD Integration

The version management system integrates with CI/CD:

```yaml
# Example GitHub Action step
- name: Verify Version Consistency
  run: python update_version.py --check

- name: Update Version for Release
  run: python update_version.py --set ${{ github.event.inputs.version }}
```

## Troubleshooting

### Common Issues

**Q: Version inconsistency detected**
```bash
# Fix automatically
python update_version.py
```

**Q: VERSION file not found**
```bash
# Ensure you're in the repository root
cd path/to/spiderfoot
python update_version.py --check
```

**Q: Permission denied on file updates**
```bash
# Check file permissions
ls -la VERSION docs/conf.py
chmod 644 VERSION docs/conf.py
```

### Manual Recovery

If the automated system fails:

1. **Check VERSION file**:
   ```bash
   cat VERSION
   ```

2. **Manually update if needed**:
   ```bash
   echo "5.2.1" > VERSION
   ```

3. **Run full update**:
   ```bash
   python update_version.py
   ```

## Technical Details

### Version Reading Logic

The `spiderfoot/__version__.py` module:

```python
def _get_version():
    """Read version from the VERSION file in the repository root."""
    try:
        version_file = pathlib.Path(__file__).parent.parent / "VERSION"
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except (FileNotFoundError, IOError):
        return "5.2.1"  # Fallback version

__version__ = _get_version()
```

### Update Patterns

The utility uses regex patterns to find and update versions:

- Badge versions: `version-X.Y.Z--Enterprise`
- Release links: `/releases/tag/vX.Y.Z`
- Docker images: `spiderfoot:vX.Y.Z`
- Documentation: `Version X.Y.Z`, `SpiderFoot X.Y.Z`

## Integration Examples

### Python Module Usage

```python
from spiderfoot import __version__
print(f"SpiderFoot version: {__version__}")
```

### Web Interface

```python
return templ.render(version=__version__, ...)
```

### API Response

```python
return {"status": "ok", "version": __version__}
```

### CLI Tools

```python
print(f"SpiderFoot {__version__}: Open Source Intelligence Automation.")
```

## Security Considerations

- **Version file integrity**: The VERSION file should be protected from unauthorized changes
- **Build reproducibility**: Version consistency ensures reproducible builds
- **Audit trail**: All version changes should be tracked in git history
- **Validation**: The utility validates version format to prevent invalid versions

## Future Enhancements

Planned improvements to the version management system:

1. **Automated pre-commit hooks** to verify version consistency
2. **Integration with semantic release tools** for automated versioning
3. **Version changelog generation** from git commits
4. **Release notes automation** based on version changes
5. **Dependency version management** for requirements.txt

---

For questions or issues with version management, please refer to the [Contributing Guide](contributing.md) or open an issue on GitHub.
