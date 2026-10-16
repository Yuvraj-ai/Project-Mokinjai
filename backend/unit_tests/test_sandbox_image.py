"""The sandbox image, and the exact isolation it runs under.

Every test here is marked `docker`. It needs a reachable socket *and* the image; the
suite skips the whole file otherwise (see conftest.pytest_collection_modifyitems), so
a machine without either stays green. To actually run it:

    newgrp docker -c "cd backend && ./venv/bin/python -m pytest unit_tests/test_sandbox_image.py -q -m docker"

`newgrp` is the working bridge for a process that predates the `docker` group — `sg`
is not installed here and `setpriv --groups` fails. To opt in explicitly:

    MOKINJAY_SANDBOX_DOCKER=1 ./venv/bin/python -m pytest unit_tests/test_sandbox_image.py -q
"""

import subprocess

import pytest

from app.services.sandbox.backends import SandboxConfig

pytestmark = pytest.mark.docker

IMAGE = "mokinjay-sandbox:1"


def run(*args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


class TestTheImageExists:
    def test_the_image_is_built(self):
        assert run("docker", "image", "inspect", IMAGE).returncode == 0, (
            f"{IMAGE} is not built. Build it with:\n"
            "    docker build -f docker/Dockerfile.sandbox -t mokinjay-sandbox:1 ."
        )

    def test_the_kernel_is_baked_in(self):
        result = run("docker", "run", "--rm", "--entrypoint", "test", IMAGE, "-f", "/app/kernel.py")

        assert result.returncode == 0

    def test_the_libraries_are_installed(self):
        result = run(
            "docker", "run", "--rm", "--network", "none", "--entrypoint", "python", IMAGE,
            "-c", "import pandas, openpyxl, docx, pypdf; print('ok')",
        )

        assert result.stdout.strip() == "ok", result.stderr or result.stdout


class TestTheIsolation:
    def test_the_root_filesystem_is_read_only(self):
        result = run(
            "docker", "run", "--rm", "--read-only", "--entrypoint", "sh", IMAGE,
            "-c", "touch /nope 2>&1 || echo refused",
        )

        assert "refused" in result.stdout

    def test_there_is_no_network(self):
        result = run(
            "docker", "run", "--rm", "--network", "none", "--entrypoint", "python", IMAGE,
            "-c",
            "import socket\n"
            "s = socket.socket()\n"
            "s.settimeout(2)\n"
            "try:\n"
            "    s.connect(('1.1.1.1', 80))\n"
            "    print('reached')\n"
            "except OSError:\n"
            "    print('blocked')\n",
        )

        assert result.stdout.strip() == "blocked"

    def test_the_process_is_not_root(self):
        result = run("docker", "run", "--rm", "--user", "1000:1000", "--entrypoint", "id", IMAGE, "-u")

        assert result.stdout.strip() == "1000"

    def test_the_output_mount_is_writable_within_its_limit(self):
        result = run(
            "docker", "run", "--rm", "--read-only", "--user", "1000:1000",
            "--tmpfs", "/app/output:size=64m,mode=1777", "--workdir", "/app",
            "--entrypoint", "python", IMAGE,
            "-c",
            "open('/app/output/x.txt', 'w').write('written')\n"
            "print(open('/app/output/x.txt').read())\n",
        )

        assert result.stdout.strip() == "written", result.stderr or result.stdout

    def test_the_memory_limit_is_applied(self):
        result = run(
            "docker", "run", "--rm", "--memory", "256m", "--network", "none", "--entrypoint", "sh", IMAGE,
            "-c", "cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.limit_in_bytes",
        )

        assert int(result.stdout.strip()) == 256 * 1024 * 1024
