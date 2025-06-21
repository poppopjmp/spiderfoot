# SpiderFoot Documentation

This directory contains the complete documentation for SpiderFoot Enterprise.

## Building Documentation

### Prerequisites

1. Install documentation dependencies:
```bash
pip install -r docs/requirements.txt
```

### Quick Build

Use the provided build script:

```bash
# Complete documentation build
python build_docs.py --all

# Just build HTML docs
python build_docs.py

# Build and serve locally
python build_docs.py --serve
```

### Manual Build

Alternatively, build manually:

```bash
# On Windows
cd docs
make.bat html

# On Unix/Linux/macOS
cd docs
make html
```

### Output

Built documentation will be available in `docs/_build/html/index.html`

## Documentation Structure

```
docs/
├── index.rst                          # Main documentation index
├── README.md                          # Documentation overview
├── PRODUCTION_READY.md                # Production deployment summary
├── installation.md                    # Installation guide
├── quickstart.md                      # Quick start guide
├── configuration.md                   # Configuration guide
├── basic_usage.md                     # Basic usage guide
├── cli_usage.md                       # CLI usage guide
├── modules_guide.md                   # Modules documentation
├── docker_deployment.md               # Docker deployment
├── enterprise_deployment.md           # Enterprise deployment
├── webhook_integration.md             # Webhook integration
├── web_interface.md                   # Web interface guide
├── python_api.md                      # Python API reference
├── security_considerations.md         # Security considerations
├── troubleshooting.md                 # Troubleshooting guide
├── contributing.md                    # Contribution guidelines
├── VERSION_MANAGEMENT.md              # Version management
├── advanced/                          # Advanced topics
│   ├── enterprise_storage.md          # Advanced storage
│   ├── ai_threat_intelligence.md      # AI features
│   ├── security_hardening.md          # Security hardening
│   └── performance_optimization.md    # Performance optimization
├── api/                               # API documentation
│   └── rest_api.md                    # REST API reference
├── user_guide/                        # User guides
│   ├── basic_usage.md                 # Basic usage
│   ├── web_interface.md               # Web interface
│   ├── cli_usage.md                   # CLI usage
│   └── modules_guide.md               # Module guide
├── workflow/                          # Workflow documentation
│   ├── getting_started.md             # Workflow basics
│   ├── multi_target_scanning.md       # Multi-target workflows
│   ├── correlation_analysis.md        # Correlation features
│   └── cti_reports.md                 # CTI reporting
├── developer/                         # Developer documentation
│   ├── module_development.md          # Module development
│   └── api_development.md             # API development
└── modules/                           # Module-specific docs
    ├── index.md                       # Module index
    └── custom_modules.md              # Custom modules
```

## Common Issues and Solutions

### Sphinx Not Found

If you get "sphinx-build command not found":

```bash
pip install -r docs/requirements.txt
```

### Missing Dependencies

If markdown files aren't processing correctly:

```bash
pip install myst-parser sphinx-copybutton
```

### Build Warnings

Common warnings and solutions:

1. **Reference target not found**: Check that all files referenced in `index.rst` exist
2. **Duplicate label**: Ensure section headers are unique across files
3. **Image not found**: Verify image paths in `docs/images/` directory

### Link Checking

Check for broken links:

```bash
python build_docs.py --check-links
```

## Contributing to Documentation

1. Follow markdown best practices:
   - Use proper heading hierarchy
   - Include code examples with syntax highlighting
   - Add newlines between sections
   - Use consistent formatting

2. Test your changes:
   - Build documentation locally
   - Check for warnings and errors
   - Verify links work correctly

3. Update index.rst if adding new files

## Markdown Style Guide

### Headers
```markdown
# Main Title (H1)
## Section (H2)
### Subsection (H3)
#### Sub-subsection (H4)
```

### Code Blocks
```markdown
\`\`\`python
# Python code example
import spiderfoot
\`\`\`

\`\`\`bash
# Shell command example
python sf.py --help
\`\`\`
```

### Links
```markdown
[Link text](filename.md)
[External link](https://example.com)
```

### Lists
```markdown
- Bullet item 1
- Bullet item 2

1. Numbered item 1
2. Numbered item 2
```

### Admonitions
```markdown
```{note}
This is a note
```

```{warning}
This is a warning
```

```{tip}
This is a tip
```
\`\`\`
```

## Updating Documentation

When updating documentation:

1. Keep content aligned with current codebase
2. Update version numbers in conf.py when making releases
3. Ensure all examples work with current version
4. Update screenshots and UI references as needed
5. Maintain consistency in terminology and formatting

## Documentation Dependencies

The documentation uses:

- **Sphinx**: Documentation generator
- **MyST Parser**: Modern markdown parser for Sphinx
- **sphinx-rtd-theme**: Read the Docs theme
- **sphinx-copybutton**: Copy button for code blocks

For the complete list, see `docs/requirements.txt`.

## Accessing Documentation

### Sphinx-Generated Documentation

After building with Sphinx, documentation is available at:
- **Local file**: `docs/_build/html/index.html`
- **Local server**: http://localhost:8000 (when using `--serve`)

### Web UI Documentation

SpiderFoot includes built-in documentation accessible through the web interface:

1. **Start SpiderFoot**: `python sf.py -l 127.0.0.1:5001`
2. **Access Documentation**: Navigate to http://127.0.0.1:5001/documentation
3. **Browse Topics**: Use the sidebar navigation to explore different topics

The web UI documentation features:
- **Interactive Navigation**: Easy browsing with sidebar menu
- **AJAX Loading**: Fast content loading without page refreshes
- **Markdown Rendering**: Rich formatting with code highlighting
- **Responsive Design**: Works on desktop and mobile devices

### Documentation Formats

SpiderFoot documentation is available in multiple formats:

| Format | Location | Use Case |
|--------|----------|----------|
| **Web UI** | http://127.0.0.1:5001/documentation | Interactive browsing during usage |
| **Sphinx HTML** | `docs/_build/html/` | Offline documentation |
| **Markdown Files** | `docs/` directory | Direct file reading |
| **PDF** | `docs/_build/latex/` | Printable documentation |

### Requirements for Web UI Documentation

The web UI documentation requires:
- **Markdown library**: `pip install markdown>=3.4.0`
- **Proper file structure**: All `.md` files in `docs/` directory
- **Running SpiderFoot**: Web server must be active
