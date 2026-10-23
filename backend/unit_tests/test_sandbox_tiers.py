"""Tier sizing, the pinned swap limit, and the per-workspace memory budget."""

import pytest

from app.services.sandbox import budget
from app.services.sandbox.backends import MAX_FILE_BYTES, SandboxConfig, TIERS
from app.services.sandbox.docker_backend import DockerBackend

MIB = 2**20


@pytest.fixture(autouse=True)
def clean_budget():
    budget.reset()
    yield
    budget.reset()


@pytest.mark.parametrize(
    "size,memory,cpus,tmpfs",
    [
        (0, "256m", "0.5", 64),
        (9 * MIB, "256m", "0.5", 64),
        (10 * MIB, "512m", "0.5", 128),
        (50 * MIB, "1g", "1.0", 256),
        (95 * MIB, "2g", "1.0", 512),
    ],
)
def test_the_tier_follows_the_largest_file(size, memory, cpus, tmpfs):
    config = SandboxConfig().tiered(size)

    assert (config.memory, config.cpus) == (memory, cpus)
    assert config.work_tmpfs_mb == config.output_tmpfs_mb == tmpfs


def test_a_file_over_the_ceiling_is_refused():
    with pytest.raises(ValueError):
        SandboxConfig().tiered(MAX_FILE_BYTES + 1)


def test_the_table_is_ordered_and_ends_at_the_ceiling():
    thresholds = [row[0] for row in TIERS]

    assert thresholds == sorted(thresholds)
    assert thresholds[-1] == MAX_FILE_BYTES


def test_memory_swap_is_pinned_to_memory(tmp_path):
    spec = SandboxConfig().tiered(60 * MIB).container_spec(run_id="x", host_root=str(tmp_path))

    assert spec.memory_swap == spec.memory == "1g"


def test_the_docker_command_passes_memory_swap(tmp_path):
    spec = SandboxConfig().tiered(60 * MIB).container_spec(run_id="x", host_root=str(tmp_path))
    command = DockerBackend(spec)._run_command()

    memory_at = command.index("--memory")
    swap_at = command.index("--memory-swap")
    assert command[memory_at + 1] == "1g"
    assert command[swap_at + 1] == "1g"


def test_a_workspace_over_4096_mb_is_refused():
    assert budget.reserve("ws", 2048) is True
    assert budget.reserve("ws", 2048) is True

    assert budget.reserve("ws", 1) is False
    assert budget.used_mb("ws") == 4096


def test_releasing_returns_the_budget():
    budget.reserve("ws", 2048)
    budget.release("ws", 2048)

    assert budget.used_mb("ws") == 0
    assert budget.reserve("ws", 4096) is True


def test_releasing_more_than_reserved_does_not_go_negative():
    budget.reserve("ws", 512)
    budget.release("ws", 4096)

    assert budget.used_mb("ws") == 0


def test_another_workspace_is_unaffected():
    assert budget.reserve("one", 4096) is True

    assert budget.reserve("two", 2048) is True
    assert budget.used_mb("two") == 2048


def test_the_upload_ceiling_matches_the_sandbox_ceiling():
    from app.config import get_settings

    assert get_settings().STORAGE_MAX_UPLOAD_BYTES == MAX_FILE_BYTES
