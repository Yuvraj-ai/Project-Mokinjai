"""The skills table.

A skill is a workspace-scoped markdown pack: `description` is the one-line menu
entry the LLM sees at startup, `content` is the full body that carries `@` and
`/` references. References are parsed from `content` on read, never stored, so
there is nothing here for them to drift against.
"""

from sqlalchemy import select

from app.models.skill import Skill
from app.models.workspace import Workspace


async def test_skill_persists_and_round_trips(db_session, test_workspace):
    db_session.add(
        Skill(
            workspace_id=test_workspace.id,
            name="Writer",
            description="Sets the tone.",
            content="Prefer short sentences.",
        )
    )
    await db_session.commit()

    found = (
        await db_session.execute(select(Skill).where(Skill.name == "Writer"))
    ).scalar_one()

    assert found.workspace_id == test_workspace.id
    assert found.description == "Sets the tone."
    assert found.content == "Prefer short sentences."
    assert found.created_at is not None, "created_at should come from the server default"
    assert found.updated_at is not None, "updated_at should come from the server default"


async def test_the_same_name_is_allowed_in_two_workspaces(db_session, test_workspace, test_user):
    other = Workspace(name="Other Workspace", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()

    db_session.add_all(
        [
            Skill(workspace_id=test_workspace.id, name="Writer", description="A.", content="A."),
            Skill(workspace_id=other.id, name="Writer", description="B.", content="B."),
        ]
    )
    await db_session.commit()

    rows = (await db_session.execute(select(Skill).where(Skill.name == "Writer"))).scalars().all()

    assert len(rows) == 2
