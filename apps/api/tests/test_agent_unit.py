from datetime import UTC, datetime, timedelta

from app.agents.service import HEARTBEAT_OFFLINE_SECONDS, AgentService, hash_token
from app.models.agent import AgentStatus, ConnectorAgent


def test_hash_token_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("x")) == 64


def test_effective_status_offline_after_stale_heartbeat() -> None:
    svc = AgentService(db=None)  # type: ignore[arg-type]
    agent = ConnectorAgent(
        name="a",
        agent_key_hash="h",
        status=AgentStatus.ONLINE,
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=HEARTBEAT_OFFLINE_SECONDS + 1),
        created_by_user_id=None,  # type: ignore[arg-type]
        workspace_id=None,  # type: ignore[arg-type]
    )
    assert svc._effective_status(agent) == AgentStatus.OFFLINE


def test_effective_status_online_recent() -> None:
    svc = AgentService(db=None)  # type: ignore[arg-type]
    agent = ConnectorAgent(
        name="a",
        agent_key_hash="h",
        status=AgentStatus.ONLINE,
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=10),
        created_by_user_id=None,  # type: ignore[arg-type]
        workspace_id=None,  # type: ignore[arg-type]
    )
    assert svc._effective_status(agent) == AgentStatus.ONLINE


def test_effective_status_revoked() -> None:
    svc = AgentService(db=None)  # type: ignore[arg-type]
    agent = ConnectorAgent(
        name="a",
        agent_key_hash="h",
        status=AgentStatus.REVOKED,
        revoked_at=datetime.now(UTC),
        last_heartbeat_at=datetime.now(UTC),
        created_by_user_id=None,  # type: ignore[arg-type]
        workspace_id=None,  # type: ignore[arg-type]
    )
    assert svc._effective_status(agent) == AgentStatus.REVOKED
