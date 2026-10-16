"""The tools table.

Code is canonical and nothing derived is stored, so these tests pin the column
list as much as they pin the round trip.
"""

from sqlalchemy import select, text

from app.models.tool import Tool


CODE = '''
def get_weather(city: str) -> str:
    """Report the weather for a city.

    Args:
        city: The city to report on.
    """
    return city
'''


def test_the_table_stores_no_derived_column():
    """The description, the parameters and the schema are extracted on read."""
    assert set(Tool.__table__.columns.keys()) == {
        "id",
        "workspace_id",
        "name",
        "code",
        "created_at",
        "updated_at",
    }


async def test_a_tool_round_trips_through_the_database(db_session, test_workspace):
    db_session.add(Tool(workspace_id=test_workspace.id, name="get_weather", code=CODE))
    await db_session.commit()

    found = (
        await db_session.execute(select(Tool).where(Tool.name == "get_weather"))
    ).scalar_one()

    assert found.workspace_id == test_workspace.id
    assert found.code == CODE
    assert found.created_at is not None, "created_at should come from the server default"
    assert found.updated_at is not None, "updated_at should come from the server default"


async def test_deleting_a_workspace_deletes_its_tools(db_session, test_workspace):
    """The foreign key does the work: a workspace's tools do not outlive it.

    Deleted through SQL rather than the ORM so the database constraint is what is
    exercised. An ORM delete would have to load the relationship first, which is an
    async lazy load away from a different failure than the one under test.
    """
    db_session.add(Tool(workspace_id=test_workspace.id, name="get_weather", code=CODE))
    await db_session.commit()

    await db_session.execute(
        text("DELETE FROM workspaces WHERE id = :id"), {"id": test_workspace.id}
    )
    await db_session.commit()

    assert (await db_session.execute(select(Tool))).scalars().all() == []
