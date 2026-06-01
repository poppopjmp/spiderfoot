# Security Policy

## Supported Versions

Security fixes are applied to the latest released minor version. Older versions
may not receive backported fixes.

| Version | Supported          |
| ------- | ------------------ |
| 6.0.x   | :white_check_mark: |
| < 6.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, report them privately using one of the following channels:

- **GitHub Security Advisories** (preferred): open a private advisory at
  <https://github.com/poppopjmp/spiderfoot/security/advisories/new>.
- **Email**: send details to the maintainer at <van1sh@van1shland.io>.

Please include as much of the following as you can:

- The type of issue (e.g. SSRF, injection, auth bypass, RCE, info disclosure).
- The affected component (module, API router, service) and version/commit.
- Step-by-step reproduction instructions and any proof-of-concept.
- The impact and how an attacker might exploit it.

## Response Targets

| Stage                        | Target            |
| ---------------------------- | ----------------- |
| Acknowledgement of report    | within 3 business days |
| Initial assessment / triage  | within 7 business days |
| Fix or mitigation timeline   | communicated after triage |

We will keep you informed of progress and credit you in the release notes
(unless you prefer to remain anonymous).

## Disclosure Policy

We follow coordinated disclosure. Please give us a reasonable opportunity to
release a fix before any public disclosure. We aim to disclose fixed
vulnerabilities in the [CHANGELOG](CHANGELOG.md) under a `### Security` heading.

## Scope

SpiderFoot is an OSINT/attack-surface tool that, by design, performs network
requests against user-specified targets. Reports about SpiderFoot *scanning a
target you configured it to scan* are out of scope. In-scope issues include,
for example:

- Authentication/authorization bypass in the API or web UI.
- Injection (SQL, command, template) in the application itself.
- SSRF that lets a user reach internal infrastructure they could not otherwise.
- Secret/credential leakage by the application.
- Remote code execution in the application or its container images.

## Security Hardening

For operational hardening guidance (TLS, secrets, rate limiting, container
runtime), see [`documentation/security.md`](documentation/security.md).
