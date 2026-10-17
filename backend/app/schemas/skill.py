from datetime import datetime

from pydantic import BaseModel, Field

# A skill name is written as `@Name`, so it carries the same identifier pattern
# a structured-output definition name does. A name that fails this could be saved
# but never referenced, and the `@` picker would offer an unusable entry.
SKILL_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_]*$"

# The description is injected verbatim into the system-prompt menu. Progressive
# disclosure only works if the disclosed thing is small, so it is capped.
SKILL_DESCRIPTION_MAX = 200


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=SKILL_NAME_PATTERN)
    description: str = Field(min_length=1, max_length=SKILL_DESCRIPTION_MAX)
    content: str = Field(min_length=1)


class SkillUpdate(SkillCreate):
    pass


class SkillResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    content: str
    skill_refs: list[str] = Field(default_factory=list)
    tool_refs: list[str] = Field(default_factory=list)
    referenced_by: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]
    total: int


class ReferenceMenuEntry(BaseModel):
    name: str
    description: str


class ReferenceMenuResponse(BaseModel):
    """What the editor's `@` and `/` pickers can offer."""

    skills: list[ReferenceMenuEntry]
    tools: list[ReferenceMenuEntry]
