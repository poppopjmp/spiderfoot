# Contributing to SpiderFoot

Thank you for your interest in contributing to SpiderFoot! This guide covers everything you need to get started.

---

## Code of Conduct

Be respectful, constructive, and inclusive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (frontend)
- Go 1.21+ (CLI)
- Docker & Docker Compose v2
- PostgreSQL 15+ (or use the Docker stack)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot

# Start core services
docker compose up -d

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Run tests
pytest
cd frontend && npm test && cd ..
```

---

## Development Workflow

1. **Fork** the repository and create a feature branch from `main`
2. **Write code** following the style guidelines below
3. **Add tests** for new functionality
4. **Run checks** before submitting:
   ```bash
   # Python linting
   flake8 spiderfoot/ modules/ --max-line-length=120

   # Type checking
   mypy spiderfoot/ --ignore-missing-imports

   # Python tests
   pytest

   # Frontend tests
   cd frontend && npm test
   ```
5. **Commit** with clear, descriptive messages (see [Commit Messages](#commit-messages))
6. **Open a Pull Request** against `main`

---

## Code Style

### Python

- **PEP 8** with `max-line-length = 120`
- **Type annotations** on all public functions and methods (see `setup.cfg` `[mypy]` section)
- **Docstrings** in Google style for all public APIs
- Imports: stdlib → third-party → local, separated by blank lines
- Use `| None` instead of `Optional[T]` for union types (PEP 604)

### TypeScript (Frontend)

- **ESLint + Prettier** enforced — run `npm run lint`
- **Strict mode** enabled — `tsc --noEmit` must pass with zero errors
- Use React Query (`@tanstack/react-query`) for server state
- Prefer named exports over default exports

### Go (CLI)

- `go vet` and `go test -race` must pass
- Follow standard Go project layout

---

## Writing Modules

SpiderFoot modules go in `modules/`. Two base classes are available:

| Base Class | When to Use |
|-----------|-------------|
| `SpiderFootPlugin` | Standard synchronous modules |
| `SpiderFootAsyncPlugin` | Modules with many HTTP/DNS calls that benefit from native async I/O |

See the [Module Migration Guide](documentation/MODULE_MIGRATION_GUIDE.md) for moving legacy modules to the modern plugin system, and the [Async Plugin Guide](documentation/async_plugin_guide.md) for writing async modules.

---

## Type Checking

The project uses **PEP 561** (`py.typed` marker) and **mypy** for static type analysis:

```bash
mypy spiderfoot/ --ignore-missing-imports
```

Configuration is in `setup.cfg` under `[mypy]`:
- `python_version = 3.11`
- `check_untyped_defs = true`
- `no_implicit_optional = true`

When adding new code, always include return type annotations and parameter types.

---

## Commit Messages

Use conventional commit prefixes:

| Prefix | Usage |
|--------|-------|
| `feat(scope):` | New feature |
| `fix(scope):` | Bug fix |
| `docs(scope):` | Documentation only |
| `refactor(scope):` | Code restructuring |
| `test(scope):` | Adding/updating tests |
| `ci(scope):` | CI/CD changes |
| `security(scope):` | Security improvements |

Example: `feat(engine): native async I/O via aiohttp + aiodns`

---

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include a clear description of **what** changed and **why**
- Reference related issues with `Closes #123`
- Ensure CI passes before requesting review
- Update documentation if public APIs change

---

## Reporting Issues

Use [GitHub Issues](https://github.com/smicallef/spiderfoot/issues) with the appropriate template:

- **Bug Report**: Include steps to reproduce, expected vs actual behavior, environment details
- **Feature Request**: Describe the use case, proposed solution, and alternatives considered

---

## Questions?

- Check the [FAQ](documentation/faq.md)
- Read the [Troubleshooting Guide](documentation/troubleshooting.md)
- Open a [Discussion](https://github.com/smicallef/spiderfoot/discussions)
