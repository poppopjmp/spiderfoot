# Contributing to SpiderFoot

We welcome contributions to SpiderFoot! This guide will help you get started with contributing code, documentation, or bug reports.

## Getting Started

### Prerequisites
- Python 3.7 or higher
- Git
- Basic understanding of OSINT concepts
- Familiarity with web development (for UI contributions)

### Development Setup

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/yourusername/spiderfoot.git
cd spiderfoot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start development server
python sf.py -l 127.0.0.1:5001
```

## Ways to Contribute

### 1. Bug Reports
- Use GitHub Issues to report bugs
- Include steps to reproduce
- Provide system information
- Include relevant log output

### 2. Feature Requests
- Open a GitHub Issue with enhancement label
- Describe the use case clearly
- Explain expected behavior
- Consider implementation complexity

### 3. Code Contributions
- Bug fixes
- New modules
- Performance improvements
- UI enhancements
- Documentation updates

### 4. Documentation
- API documentation
- Module documentation
- User guides
- Installation instructions

## Development Guidelines

### Version Management

SpiderFoot uses a centralized version management system:

- **Never manually edit version numbers** in individual files
- **Use the version utility**: `python update_version.py` for all version changes  
- **Check consistency**: Run `python update_version.py --check` before submitting PRs
- **Version format**: Follow semantic versioning (X.Y.Z)

For detailed information, see the [Version Management Guide](VERSION_MANAGEMENT.md).

### Code Style
- Follow PEP 8 for Python code
- Use meaningful variable names
- Add docstrings for functions and classes
- Keep functions focused and small

### Module Development
- See [Module Development Guide](developer/module_development.md)
- Follow existing module patterns
- Include proper error handling
- Add configuration options where appropriate

### Testing
```bash
# Run tests
python -m pytest tests/

# Test specific module
python sf.py -s example.com -t DOMAIN_NAME -m your_module -v

# Validate module
python -m py_compile modules/your_module.py
```

## Submitting Changes

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write clean, documented code
   - Add tests where appropriate
   - Update documentation

3. **Test Changes**
   ```bash
   # Test your module
   python sf.py -s example.com -t DOMAIN_NAME -m your_module
   
   # Run existing tests
   python -m pytest
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub
   ```

### PR Requirements
- Clear description of changes
- Reference related issues
- Include tests for new features
- Update documentation as needed
- Follow coding standards

## Module Development

### Module Template
```python
from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_your_module(SpiderFootPlugin):
    meta = {
        'name': "Your Module Name",
        'summary': "Brief description of what the module does",
        'flags': [""],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["DNS"],
        'dataSource': {
            'website': "https://example.com",
            'model': "FREE_NOAUTH_UNLIMITED"
        }
    }

    opts = {
        'timeout': 30,
        'verify': True
    }

    optdescs = {
        'timeout': "Timeout for requests in seconds",
        'verify': "Verify hostnames resolve"
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["DOMAIN_NAME"]

    def producedEvents(self):
        return ["IP_ADDRESS"]

    def handleEvent(self, event):
        # Your module logic here
        pass
```

### Best Practices
- Handle errors gracefully
- Respect API rate limits
- Use appropriate timeouts
- Validate input data
- Follow naming conventions

## Documentation

### Writing Documentation
- Use clear, concise language
- Include practical examples
- Update existing docs when making changes
- Follow markdown formatting standards

### Documentation Structure
```
docs/
├── README.md                 # Main overview
├── installation.md          # Installation guide
├── quickstart.md            # Quick start guide
├── user_guide/             # User documentation
├── modules/                # Module documentation
├── api/                    # API documentation
└── developer/              # Developer guides
```

## Community

### Communication Channels
- **GitHub Issues**: Bug reports and feature requests
- **Discord**: Real-time community chat
- **GitHub Discussions**: General discussions
- **Twitter**: Updates and announcements

### Community Guidelines
- Be respectful and professional
- Help others when possible
- Follow code of conduct
- Share knowledge and experiences

## Recognition

Contributors are recognized in:
- GitHub contributors list
- Release notes
- Documentation credits
- Community acknowledgments

## Getting Help

### Resources
- [Development Documentation](developer/module_development.md)
- [API Reference](api/rest_api.md)
- [Module Examples](modules/index.md)
- [Community Discord](https://discord.gg/vyvztrG)

### Contact
- GitHub Issues for bugs/features
- Discord for real-time help
- Email maintainers for security issues

Thank you for contributing to SpiderFoot!
