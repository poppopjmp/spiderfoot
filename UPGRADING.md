# Upgrading SpiderFoot

This guide explains how to adopt a new SpiderFoot release and what to expect.
For the full list of changes see [`CHANGELOG.md`](CHANGELOG.md).

---

## Upgrading to v6.1.0 (from 6.0.x)

**v6.1.0 is a hardening and test-maturity release.** There are **no breaking
changes**: no API, configuration, database-schema, or CLI changes. You can
upgrade in place.

- **No database migration is required** — the schema is unchanged.
- **No configuration changes are required** — existing `.env` / config files
  keep working.
- SpiderFoot remains **PostgreSQL-only** (since 6.0.0) and requires **Python
  3.10–3.13**.

### How to upgrade

Pick the path that matches your deployment.

#### Docker Compose (recommended)
```bash
git pull                      # get the v6.1.0 sources (or checkout the tag)
docker compose pull           # pull the rebuilt images
docker compose up -d          # recreate containers (add your profiles, e.g. --profile full)
```
Your PostgreSQL/Redis/MinIO volumes are preserved; existing scans and config
carry over.

#### Helm (Kubernetes)
The chart is **0.4.0** with `appVersion: 6.1.0`.
```bash
helm repo update
helm upgrade spiderfoot ./helm/spiderfoot   # or your chart repo reference
```

#### From source (pip / development)
```bash
git pull
pip install -r requirements.txt   # dependencies unchanged for 6.1.0
```

### Verify the upgrade
```bash
# Python package
python -c "import spiderfoot; print(spiderfoot.__version__)"   # -> 6.1.0

# Running API
curl -s http://localhost:8001/health        # readiness
# the API version endpoint also reports app_version 6.1.0
```

---

## Behavioural corrections to be aware of

v6.1.0 fixes several **silent correctness/security bugs**. The fixes are
improvements, but because they change how some events are *classified*, your
scan results may shift slightly compared with 6.0.x. None of these require
action — they are listed so the changes are expected, not surprising.

| Area | Before (6.0.x) | After (6.1.0) |
|------|----------------|---------------|
| **Private IPs** (`10.x`, `172.16–31.x`, `192.168.x`) | mislabelled as public `IP_ADDRESS` | correctly classified as internal (e.g. `sfp_dnsresolve` emits `INTERNAL_IP_ADDRESS`) |
| **Link-local** `169.254.169.254` (cloud metadata) and `fe80::/10` | treated as **public** | correctly treated as non-public |
| **Scan scope matching** | case-sensitive — mixed-case hosts (`Sub.Example.COM`) wrongly out-of-scope | case-insensitive — such hosts are now correctly **in scope** (you may see more in-scope results) |
| **URL de-duplication** | non-standard ports mangled (`:8080`→`80`), distinct URLs collided and dropped | port-aware — distinct URLs are preserved (you may see more distinct URL findings) |
| **Config booleans** | could flip `True`→`False` on an in-memory round trip | persist correctly |
| **Correlation rules** | one invalid regex aborted the whole correlation run | a bad rule is skipped with a warning; others still run |

### API endpoints fixed (were previously broken)
If you integrate against the REST API, these now behave correctly:

- `POST /api/data/modules/bulk-disable` — now accepts a JSON body
  `{"module_names": [...]}` (previously always returned `400`).
- `POST /api/storage/snapshots/all` — now snapshots all collections (previously
  hit the single-collection handler).
- Literal sub-paths that were shadowed by `/{id}` routes now resolve, e.g.
  `/api/notification-rules/{stats,history,operators,channels}`,
  `/api/report-templates/{history,variables,categories,formats}`,
  `/api/tags/{stats,colors}`, `/api/webhooks/event-types`,
  `/api/scans/compare`, `/health/shutdown`.
- Unknown-resource lookups that returned `500` now return the correct `404`
  (e.g. unknown module/entity/workspace/scan).

### Rollback
v6.1.0 introduces no schema or data-format changes, so you can roll back to
6.0.x by redeploying the previous image/tag — existing data remains compatible.

---

## General upgrade guidance

- Review [`CHANGELOG.md`](CHANGELOG.md) for the target version.
- Back up your PostgreSQL database before any major (`X.0.0`) upgrade.
- Major releases (e.g. a future `7.0.0`) may include breaking changes and will
  document required migration steps in this file.
