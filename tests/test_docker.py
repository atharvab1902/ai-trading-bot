"""Tests for Docker setup — validates Dockerfile and docker-compose.yml are sane."""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


# ── static file checks (no Docker daemon needed) ─────────────────────────────

def test_dockerfile_exists():
    assert (REPO_ROOT / "Dockerfile").exists()


def test_dockercompose_exists():
    assert (REPO_ROOT / "docker-compose.yml").exists()


def test_dockerignore_exists():
    assert (REPO_ROOT / ".dockerignore").exists()


def test_dockerfile_has_python312():
    content = (REPO_ROOT / "Dockerfile").read_text()
    assert "python:3.12" in content


def test_dockerfile_installs_claude():
    content = (REPO_ROOT / "Dockerfile").read_text()
    assert "claude-code" in content or "claude" in content


def test_dockerfile_exposes_5000():
    content = (REPO_ROOT / "Dockerfile").read_text()
    assert "5000" in content


def test_dockerfile_copies_requirements():
    content = (REPO_ROOT / "Dockerfile").read_text()
    assert "requirements.txt" in content


def test_dockercompose_has_port_5000():
    content = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "5000:5000" in content


def test_dockercompose_mounts_data_volume():
    content = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "./data:/app/data" in content


def test_dockercompose_mounts_logs_volume():
    content = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "./logs:/app/logs" in content


def test_dockercompose_mounts_ml_volume():
    content = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "./ml:/app/ml" in content


def test_dockercompose_uses_env_file():
    content = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "env_file" in content
    assert ".env" in content


def test_dockercompose_has_restart_policy():
    content = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "restart" in content


def test_dockerignore_excludes_env():
    content = (REPO_ROOT / ".dockerignore").read_text()
    assert ".env" in content


def test_dockerignore_excludes_logs():
    content = (REPO_ROOT / ".dockerignore").read_text()
    assert "logs" in content


# ── Docker daemon checks (skipped if Docker not available) ────────────────────

def _docker_daemon_running() -> bool:
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
    return result.returncode == 0


docker_daemon_up = _docker_daemon_running()


@pytest.mark.skipif(not docker_daemon_up, reason="Docker daemon not running")
def test_docker_build_succeeds():
    result = subprocess.run(
        ["docker", "build", "-t", "trading-bot-test", "--no-cache", "."],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, f"Docker build failed:\n{result.stderr}"


@pytest.mark.skipif(not docker_daemon_up, reason="Docker daemon not running")
def test_docker_container_starts_dashboard():
    """Container should start and dashboard should respond on port 5001."""
    run_result = subprocess.run(
        ["docker", "run", "-d", "--name", "bot-test",
         "-p", "5001:5000", "trading-bot-test"],
        capture_output=True, text=True, timeout=30
    )
    try:
        import time, urllib.request
        time.sleep(4)
        resp = urllib.request.urlopen("http://localhost:5001", timeout=5)
        assert resp.status == 200
    finally:
        subprocess.run(["docker", "rm", "-f", "bot-test"], capture_output=True)
        subprocess.run(["docker", "rmi", "trading-bot-test"], capture_output=True)
