from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AGENT_NAME_MAX = 100
AGENT_DESCRIPTION_MAX = 2000
AGENT_PROMPT_MAX = 32_000


class AgentWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=AGENT_NAME_MAX)
    description: str | None = Field(default=None, max_length=AGENT_DESCRIPTION_MAX)
    llm_profile_id: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1, max_length=AGENT_PROMPT_MAX)
    source_prompt_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    structured_output_id: str | None = None
    web_search: dict[str, Any] | None = None
    skill_ids: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    connector_ids: list[str] = Field(default_factory=list)
    subagent_ids: list[str] = Field(default_factory=list)


class TemperatureCapabilityResponse(BaseModel):
    supported: bool
    minimum: float
    maximum: float


class ReasoningCapabilityResponse(BaseModel):
    supported: bool
    levels: list[str]
    default: str | None


class AdvancedCapabilityResponse(BaseModel):
    top_p: bool
    seed: bool
    stop: bool


class AgentCapabilitiesResponse(BaseModel):
    provider: str
    model_id: str
    max_output_tokens: int
    max_output_source: str
    temperature: TemperatureCapabilityResponse
    reasoning: ReasoningCapabilityResponse
    advanced: AdvancedCapabilityResponse
    native_web_search: bool
    structured_output: bool
    tool_calling: bool


class ResolvedSkill(BaseModel):
    id: str
    name: str
    root: bool


class ResolvedTool(BaseModel):
    name: str
    source: Literal["builtin", "workspace"]
    locked: bool
    tool_id: str | None = None


class ResolvedDependencies(BaseModel):
    skills: list[ResolvedSkill] = Field(default_factory=list)
    tools: list[ResolvedTool] = Field(default_factory=list)


class AgentResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    llm_profile_id: str | None
    system_prompt: str
    source_prompt_id: str | None
    params: dict[str, Any]
    structured_output_id: str | None
    web_search: dict[str, Any] | None
    skill_ids: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    connector_ids: list[str] = Field(default_factory=list)
    subagent_ids: list[str] = Field(default_factory=list)
    resolved: ResolvedDependencies = Field(default_factory=ResolvedDependencies)
    capabilities: AgentCapabilitiesResponse | None = None
    status: Literal["ready", "needs_attention"]
    issues: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AgentListItem(BaseModel):
    id: str
    name: str
    description: str | None
    llm_profile_id: str | None
    status: Literal["ready", "needs_attention"]
    updated_at: datetime


class AgentListResponse(BaseModel):
    agents: list[AgentListItem]
    total: int


class AgentOption(BaseModel):
    id: str
    name: str
    description: str | None = None
    provider: str | None = None
    model_id: str | None = None
    status: str | None = None
    capabilities: AgentCapabilitiesResponse | None = None


class AgentOptionsResponse(BaseModel):
    llm_profiles: list[AgentOption] = Field(default_factory=list)
    structured_outputs: list[AgentOption] = Field(default_factory=list)
    skills: list[AgentOption] = Field(default_factory=list)
    knowledge_bases: list[AgentOption] = Field(default_factory=list)
    connectors: list[AgentOption] = Field(default_factory=list)
    tools: list[AgentOption] = Field(default_factory=list)
    agents: list[AgentOption] = Field(default_factory=list)
