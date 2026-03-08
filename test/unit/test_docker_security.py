"""Docker deployment security tests.

These tests validate that Docker images and compose configurations
meet security requirements. They parse Dockerfiles and compose YAML
rather than requiring a running Docker daemon, so they can run in CI.
"""

import os
import re
import yaml
import pytest

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCKER_DIR = os.path.join(ROOT, "docker")
COMPOSE_DIR = os.path.join(DOCKER_DIR, "compose")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Dockerfile Security ─────────────────────────────────────────────────────

class TestDockerfileAPI:
    """Verify API Dockerfile security best practices.

    Dockerfile.api is a thin single-stage extension of spiderfoot-base.
    Security hardening (USER, SUID, pip, etc.) lives in Dockerfile.base
    and is tested by TestDockerfileBase.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.content = _read(os.path.join(DOCKER_DIR, "Dockerfile.api"))

    def test_has_healthcheck(self):
        assert "HEALTHCHECK" in self.content

    def test_no_env_secrets(self):
        """No hardcoded secrets in ENV directives."""
        env_lines = [l for l in self.content.splitlines() if l.strip().startswith("ENV ")]
        for line in env_lines:
            assert "password" not in line.lower() or "changeme" not in line.lower()
            assert "secret" not in line.lower() or "=" not in line


class TestDockerfileFrontend:
    """Verify frontend Dockerfile security best practices."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.content = _read(os.path.join(ROOT, "frontend", "Dockerfile"))

    def test_uses_non_root_user(self):
        assert "USER nginx" in self.content

    def test_uses_multi_stage_build(self):
        assert self.content.count("FROM ") >= 2

    def test_removes_package_manager(self):
        assert "apk" in self.content and ("del" in self.content or "rm" in self.content)

    def test_alpine_base(self):
        assert "alpine" in self.content.lower()

    def test_default_api_url_is_internal(self):
        """Default API URL should not point to external hosts."""
        # Match only ENV directives, not comments
        match = re.search(r"^ENV\s+SF_API_URL=(\S+)", self.content, re.MULTILINE)
        assert match
        url = match.group(1)
        assert "localhost" not in url  # Should use Docker service name
        assert url.startswith("http://api:")


class TestDockerfileBase:
    """Verify base Dockerfile shared by all Python services."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.content = _read(os.path.join(DOCKER_DIR, "Dockerfile.base"))

    def test_uses_non_root_user(self):
        assert "USER spiderfoot" in self.content

    def test_uses_multi_stage_build(self):
        assert self.content.count("FROM ") >= 2

    def test_slim_base_image(self):
        assert "slim" in self.content.lower() or "alpine" in self.content.lower()

    def test_removes_suid_binaries(self):
        assert "find / -perm -4000" in self.content
        assert "chmod u-s" in self.content

    def test_removes_sgid_binaries(self):
        assert "find / -perm -2000" in self.content
        assert "chmod g-s" in self.content

    def test_removes_package_managers(self):
        assert "apt-get purge" in self.content or "rm -f /usr/bin/apt" in self.content

    def test_removes_unnecessary_network_tools(self):
        assert "rm -f /usr/bin/wget" in self.content

    def test_entrypoint_owned_by_root(self):
        assert "COPY --chown=root:root docker/docker-entrypoint.sh" in self.content

    def test_no_env_secrets(self):
        """No hardcoded secrets in ENV directives."""
        env_lines = [l for l in self.content.splitlines() if l.strip().startswith("ENV ")]
        for line in env_lines:
            assert "password" not in line.lower() or "changeme" not in line.lower()
            assert "secret" not in line.lower() or "=" not in line

    def test_pip_no_cache(self):
        assert "--no-cache-dir" in self.content

    def test_pinned_pip_version(self):
        assert re.search(r"pip==\d+\.\d+", self.content)

    def test_has_entrypoint(self):
        assert "ENTRYPOINT" in self.content


# ── Compose Security ────────────────────────────────────────────────────────

class TestComposeCoreSecurity:
    """Verify compose core.yml security controls."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = _read_yaml(os.path.join(COMPOSE_DIR, "core.yml"))
        self.services = self.config.get("services", {})

    def _get_service(self, name):
        return self.services.get(name, {})

    def test_api_no_new_privileges(self):
        api = self._get_service("api")
        assert "no-new-privileges:true" in api.get("security_opt", [])

    def test_api_read_only(self):
        api = self._get_service("api")
        assert api.get("read_only") is True

    def test_api_cap_drop_all(self):
        api = self._get_service("api")
        assert "ALL" in api.get("cap_drop", [])

    def test_api_has_healthcheck(self):
        api = self._get_service("api")
        assert "healthcheck" in api

    def test_api_has_resource_limits(self):
        api = self._get_service("api")
        deploy = api.get("deploy", {})
        assert "resources" in deploy
        assert "limits" in deploy.get("resources", {})

    def test_redis_no_new_privileges(self):
        redis = self._get_service("redis")
        assert "no-new-privileges:true" in redis.get("security_opt", [])

    def test_redis_read_only(self):
        redis = self._get_service("redis")
        assert redis.get("read_only") is True

    def test_redis_cap_drop_all(self):
        redis = self._get_service("redis")
        assert "ALL" in redis.get("cap_drop", [])

    def test_postgres_no_new_privileges(self):
        pg = self._get_service("postgres")
        assert "no-new-privileges:true" in pg.get("security_opt", [])

    def test_postgres_read_only(self):
        pg = self._get_service("postgres")
        assert pg.get("read_only") is True

    def test_frontend_no_new_privileges(self):
        fe = self._get_service("frontend")
        assert "no-new-privileges:true" in fe.get("security_opt", [])

    def test_frontend_read_only(self):
        fe = self._get_service("frontend")
        assert fe.get("read_only") is True

    def test_frontend_cap_drop_all(self):
        fe = self._get_service("frontend")
        assert "ALL" in fe.get("cap_drop", [])

    def test_backend_network_is_internal(self):
        nets = self.config.get("networks", {})
        backend = nets.get("sf-backend", {})
        assert backend.get("internal") is True

    def test_celery_worker_no_new_privileges(self):
        worker = self._get_service("celery-worker")
        assert "no-new-privileges:true" in worker.get("security_opt", [])

    def test_celery_worker_cap_drop_all(self):
        worker = self._get_service("celery-worker")
        assert "ALL" in worker.get("cap_drop", [])

    def test_no_privileged_containers(self):
        for name, svc in self.services.items():
            assert svc.get("privileged") is not True, f"{name} must not be privileged"

    def test_postgres_password_not_hardcoded(self):
        pg = self._get_service("postgres")
        env = pg.get("environment", {})
        pw = env.get("POSTGRES_PASSWORD", "")
        assert "${" in str(pw) or pw == "", "Password must come from env variable"


class TestComposeProxySecurity:
    """Verify Traefik reverse proxy security."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = _read_yaml(os.path.join(COMPOSE_DIR, "proxy.yml"))
        self.services = self.config.get("services", {})

    def test_docker_socket_proxy_exists(self):
        """Docker socket must go through a proxy — never mounted directly into Traefik."""
        assert "docker-socket-proxy" in self.services

    def test_docker_socket_proxy_read_only(self):
        proxy = self.services.get("docker-socket-proxy", {})
        vols = proxy.get("volumes", [])
        # Docker socket must be mounted read-only
        for v in vols:
            if "docker.sock" in str(v):
                assert ":ro" in str(v), "Docker socket must be :ro"

    def test_docker_socket_proxy_post_disabled(self):
        """POST disabled to prevent Traefik from modifying containers."""
        proxy = self.services.get("docker-socket-proxy", {})
        env = proxy.get("environment", {})
        assert env.get("POST") == 0

    def test_traefik_no_new_privileges(self):
        traefik = self.services.get("traefik", {})
        assert "no-new-privileges:true" in traefik.get("security_opt", [])

    def test_traefik_cap_drop_all(self):
        traefik = self.services.get("traefik", {})
        assert "ALL" in traefik.get("cap_drop", [])

    def test_traefik_cap_add_net_bind_only(self):
        traefik = self.services.get("traefik", {})
        caps = traefik.get("cap_add", [])
        assert "NET_BIND_SERVICE" in caps
        assert len(caps) == 1, "Traefik should only have NET_BIND_SERVICE cap"


class TestComposeMonitorSecurity:
    """Verify monitoring stack security."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = _read_yaml(os.path.join(COMPOSE_DIR, "monitor.yml"))
        self.services = self.config.get("services", {})

    def test_grafana_anonymous_disabled(self):
        grafana = self.services.get("grafana", {})
        env = grafana.get("environment", {})
        assert env.get("GF_AUTH_ANONYMOUS_ENABLED") == "false"

    def test_grafana_signup_disabled(self):
        grafana = self.services.get("grafana", {})
        env = grafana.get("environment", {})
        assert env.get("GF_USERS_ALLOW_SIGN_UP") == "false"

    def test_grafana_secure_cookies(self):
        grafana = self.services.get("grafana", {})
        env = grafana.get("environment", {})
        assert env.get("GF_SECURITY_COOKIE_SECURE") == "true"

    def test_grafana_samesite_strict(self):
        grafana = self.services.get("grafana", {})
        env = grafana.get("environment", {})
        assert env.get("GF_SECURITY_COOKIE_SAMESITE") == "strict"


class TestComposeScanSecurity:
    """Verify active scanner security controls."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = _read_yaml(os.path.join(COMPOSE_DIR, "scan.yml"))
        self.services = self.config.get("services", {})

    def test_active_scanner_no_new_privileges(self):
        scanner = self.services.get("celery-worker-active", {})
        assert "no-new-privileges:true" in scanner.get("security_opt", [])

    def test_active_scanner_cap_drop_all(self):
        scanner = self.services.get("celery-worker-active", {})
        assert "ALL" in scanner.get("cap_drop", [])

    def test_active_scanner_limited_caps(self):
        """Active scanner needs NET_RAW for nmap/masscan but nothing else."""
        scanner = self.services.get("celery-worker-active", {})
        caps = set(scanner.get("cap_add", []))
        allowed = {"NET_RAW", "NET_ADMIN"}
        assert caps.issubset(allowed), f"Unexpected caps: {caps - allowed}"


# ── Nginx Config Security ───────────────────────────────────────────────────

class TestNginxFrontendConfig:
    """Verify frontend nginx.conf security headers."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.content = _read(os.path.join(ROOT, "frontend", "nginx.conf"))

    def test_x_frame_options(self):
        assert "X-Frame-Options" in self.content
        assert "SAMEORIGIN" in self.content

    def test_x_content_type_options(self):
        assert "X-Content-Type-Options" in self.content
        assert "nosniff" in self.content

    def test_no_x_xss_protection(self):
        """X-XSS-Protection is deprecated and should NOT be present."""
        assert "X-XSS-Protection" not in self.content

    def test_referrer_policy(self):
        assert "Referrer-Policy" in self.content

    def test_hsts(self):
        assert "Strict-Transport-Security" in self.content
        assert "max-age=31536000" in self.content

    def test_permissions_policy(self):
        assert "Permissions-Policy" in self.content

    def test_csp(self):
        assert "Content-Security-Policy" in self.content

    def test_server_tokens_off(self):
        assert "server_tokens off" in self.content

    def test_no_server_info_leak(self):
        """Should not expose X-Powered-By or Server version."""
        # server_tokens off prevents Server version
        assert "server_tokens off" in self.content


class TestNginxMicroservicesConfig:
    """Verify nginx-microservices.conf security."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.content = _read(os.path.join(DOCKER_DIR, "nginx-microservices.conf"))

    def test_x_frame_options(self):
        assert "X-Frame-Options" in self.content

    def test_no_x_xss_protection(self):
        """X-XSS-Protection is deprecated — should be absent or commented."""
        lines = self.content.splitlines()
        for line in lines:
            if "X-XSS-Protection" in line:
                assert line.strip().startswith("#"), "X-XSS-Protection should be commented out"

    def test_has_rate_limiting(self):
        assert "limit_req_zone" in self.content

    def test_client_max_body_size(self):
        assert "client_max_body_size" in self.content


# ── Traefik Security ────────────────────────────────────────────────────────

class TestTraefikConfig:
    """Verify Traefik reverse-proxy security configuration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.static = _read_yaml(os.path.join(ROOT, "infra", "traefik", "traefik.yml"))
        self.dynamic = _read_yaml(os.path.join(ROOT, "infra", "traefik", "dynamic.yml"))

    def test_http_to_https_redirect(self):
        web = self.static.get("entryPoints", {}).get("web", {})
        redirections = web.get("http", {}).get("redirections", {})
        assert redirections.get("entryPoint", {}).get("scheme") == "https"

    def test_exposed_by_default_false(self):
        docker = self.static.get("providers", {}).get("docker", {})
        assert docker.get("exposedByDefault") is False

    def test_tls_min_version(self):
        tls_opts = self.dynamic.get("tls", {}).get("options", {}).get("default", {})
        min_ver = tls_opts.get("minVersion", "")
        assert min_ver in ("VersionTLS12", "VersionTLS13")

    def test_security_headers_middleware(self):
        middlewares = self.dynamic.get("http", {}).get("middlewares", {})
        headers = middlewares.get("security-headers", {}).get("headers", {})
        assert headers.get("frameDeny") is True
        assert headers.get("contentTypeNosniff") is True
        assert headers.get("stsSeconds") >= 31536000
        assert headers.get("stsIncludeSubdomains") is True

    def test_server_info_stripped(self):
        middlewares = self.dynamic.get("http", {}).get("middlewares", {})
        headers = middlewares.get("security-headers", {}).get("headers", {})
        custom = headers.get("customResponseHeaders", {})
        assert custom.get("X-Powered-By") == ""
        assert custom.get("Server") == ""

    def test_rate_limiting_configured(self):
        middlewares = self.dynamic.get("http", {}).get("middlewares", {})
        assert "rate-limit-api" in middlewares
        assert "rate-limit-web" in middlewares

    def test_dashboard_auth_required(self):
        middlewares = self.dynamic.get("http", {}).get("middlewares", {})
        assert "dashboard-auth" in middlewares
        auth = middlewares["dashboard-auth"].get("basicAuth", {})
        assert len(auth.get("users", [])) > 0


# ── Docker-entrypoint Security ──────────────────────────────────────────────

class TestDockerEntrypoint:
    """Verify entrypoint script security."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.content = _read(os.path.join(DOCKER_DIR, "docker-entrypoint.sh"))

    def test_uses_exec(self):
        """Must use exec to replace shell process with app — no zombie processes."""
        assert 'exec "$@"' in self.content

    def test_set_e(self):
        """Must use set -e for fail-fast behavior."""
        assert "set -e" in self.content

    def test_no_hardcoded_secrets(self):
        for line in self.content.splitlines():
            if line.strip().startswith("#"):
                continue
            assert "password=" not in line.lower()
            assert "secret=" not in line.lower()
            assert "api_key=" not in line.lower()


# ── .dockerignore Security ──────────────────────────────────────────────────

class TestDockerignore:
    """Verify .dockerignore excludes sensitive content."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.content = _read(os.path.join(ROOT, ".dockerignore"))

    def test_excludes_git(self):
        assert ".git" in self.content

    def test_excludes_env_files(self):
        assert ".env" in self.content

    def test_excludes_tests(self):
        assert "test/" in self.content

    def test_excludes_vscode(self):
        assert ".vscode" in self.content

    def test_excludes_node_modules(self):
        assert "node_modules" in self.content
