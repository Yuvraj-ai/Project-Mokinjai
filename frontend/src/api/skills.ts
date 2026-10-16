import apiClient from './client'

export interface Skill {
  id: string
  workspace_id: string
  name: string
  description: string
  content: string
  skill_refs: string[]
  tool_refs: string[]
  referenced_by: string[]
  created_at: string
  updated_at: string
}

export interface SkillInput {
  name: string
  description: string
  content: string
}

export interface ReferenceMenuEntry {
  name: string
  description: string
}

export interface ReferenceMenu {
  skills: ReferenceMenuEntry[]
  tools: ReferenceMenuEntry[]
}

/** Matches the server: a name that fails this could never be written as @Name. */
export const SKILL_NAME_PATTERN = /^[A-Za-z][A-Za-z0-9_]*$/

/** Matches the server: the menu entry the LLM sees is capped at this length. */
export const SKILL_DESCRIPTION_MAX = 200

export async function listSkills(workspaceId: string): Promise<Skill[]> {
  const response = await apiClient.get<{ skills: Skill[]; total: number }>(
    `/api/workspaces/${workspaceId}/skills`
  )
  return response.data.skills
}

export async function getSkill(workspaceId: string, skillId: string): Promise<Skill> {
  const response = await apiClient.get<Skill>(`/api/workspaces/${workspaceId}/skills/${skillId}`)
  return response.data
}

export async function createSkill(workspaceId: string, data: SkillInput): Promise<Skill> {
  const response = await apiClient.post<Skill>(`/api/workspaces/${workspaceId}/skills`, data)
  return response.data
}

export async function updateSkill(
  workspaceId: string,
  skillId: string,
  data: SkillInput
): Promise<Skill> {
  const response = await apiClient.put<Skill>(
    `/api/workspaces/${workspaceId}/skills/${skillId}`,
    data
  )
  return response.data
}

export async function deleteSkill(workspaceId: string, skillId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/skills/${skillId}`)
}

export async function getReferenceMenu(workspaceId: string): Promise<ReferenceMenu> {
  const response = await apiClient.get<ReferenceMenu>(
    `/api/workspaces/${workspaceId}/skills/reference-menu`
  )
  return response.data
}
