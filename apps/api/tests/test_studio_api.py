from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_secret
from app.models.ai import AiCredentialStatus, UserAiCredential
from app.models.document import Document, DocumentStatus, DocumentType, DocumentOrigin
from app.models.source import Source, SourceStatus, SourceType
from app.models.studio import StudioArtifactStatus
from app.spaces.service import SpaceService
from app.studio.export_pptx import export_presentation_pptx
from app.workspaces.service import WorkspaceService
from app.models.user import User
from tests.conftest import auth_cookies


def test_export_presentation_pptx_bytes() -> None:
    payload = {
        "slides": [
            {
                "title": "Intro",
                "bullets": ["Point A", "Point B"],
                "notes": "Say hello",
                "source_refs": [],
            }
        ]
    }
    data = export_presentation_pptx(payload, deck_title="Demo")
    assert data[:2] == b"PK"
    assert len(data) > 1000


@pytest.mark.asyncio
async def test_studio_create_and_poll_mocked(
    db_client: AsyncClient,
    db_session: AsyncSession,
    active_user: User,
    postgres_ready: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available")

    ws = await WorkspaceService(db_session).create(active_user, name="Studio WS", description=None)
    space, _ = await SpaceService(db_session).create(active_user, ws.id, name="Docs")
    source = Source(
        workspace_id=ws.id,
        space_id=space.id,
        type=SourceType.LOCAL,
        name="Studio Source",
        status=SourceStatus.READY,
        created_by_user_id=active_user.id,
    )
    db_session.add(source)
    await db_session.flush()
    doc = Document(
        id=uuid4(),
        workspace_id=ws.id,
        space_id=space.id,
        source_id=source.id,
        external_id="local-1",
        document_type=DocumentType.PAGE,
        title="Refund Policy",
        status=DocumentStatus.READY,
        origin=DocumentOrigin.LOCAL,
        normalized_content="Customers may request refunds within 30 days.",
    )
    db_session.add(doc)
    db_session.add(
        UserAiCredential(
            id=uuid4(),
            user_id=active_user.id,
            provider="GEMINI",
            status=AiCredentialStatus.CONNECTED,
            encrypted_api_key=encrypt_secret("test-gemini-key-1234567890"),
            key_mask="***7890",
            verified_model="gemini-flash-latest",
        )
    )
    await db_session.commit()

    async def fake_generate_json(api_key, prompt, *, preferred_model):  # noqa: ANN001
        return (
            '{"title":"Refund Deck","slides":[{"title":"Summary","bullets":["30-day window"],"notes":"Note","source_indices":[1]}]}',
            "gemini-flash-latest",
            10,
            20,
        )

    from app.studio import service as studio_service

    monkeypatch.setattr(studio_service.StudioService, "_generate_json", fake_generate_json)

    cookies = auth_cookies(active_user)
    csrf = cookies[list(cookies.keys())[1]]
    headers = {"x-csrf-token": csrf}

    create = await db_client.post(
        "/api/v1/studio/artifacts",
        json={
            "workspace_id": str(ws.id),
            "artifact_type": "PRESENTATION",
            "space_ids": [str(space.id)],
            "document_ids": [str(doc.id)],
        },
        cookies=cookies,
        headers=headers,
    )
    assert create.status_code == 202, create.text
    artifact_id = create.json()["id"]

    import asyncio

    for _ in range(30):
        get = await db_client.get(f"/api/v1/studio/artifacts/{artifact_id}", cookies=cookies)
        assert get.status_code == 200
        body = get.json()
        if body["status"] == StudioArtifactStatus.COMPLETED:
            break
        await asyncio.sleep(0.2)
    else:
        pytest.fail("Artifact did not complete in time")

    slides = body["payload_json"]["slides"]
    assert len(slides) >= 1
    assert slides[0]["title"] == "Summary"

    patch = await db_client.patch(
        f"/api/v1/studio/artifacts/{artifact_id}",
        json={"slides": [{**slides[0], "title": "Updated title"}]},
        cookies=cookies,
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["payload_json"]["slides"][0]["title"] == "Updated title"

    export = await db_client.get(
        f"/api/v1/studio/artifacts/{artifact_id}/export.pptx",
        cookies=cookies,
    )
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert export.content[:2] == b"PK"
