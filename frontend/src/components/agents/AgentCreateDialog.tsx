import { useState } from 'react'
import { AGENT_DESCRIPTION_MAX, AGENT_NAME_MAX } from '../../api/agents'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import { Input, Label } from '../ui/Field'

interface AgentCreateDialogProps {
  onContinue: (name: string, description: string) => void
  onClose: () => void
}

/** Step one: the name and description the directive asks for before the config opens. */
export default function AgentCreateDialog({ onContinue, onClose }: AgentCreateDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const valid = name.trim().length > 0

  return (
    <Modal
      open
      onClose={onClose}
      title="New agent"
      description="Name it, then configure its model and capabilities."
      width="md"
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" disabled={!valid} onClick={() => onContinue(name.trim(), description.trim())}>
            Continue
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <Label required>Name</Label>
          <Input
            autoFocus
            value={name}
            maxLength={AGENT_NAME_MAX}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && valid) onContinue(name.trim(), description.trim())
            }}
            placeholder="Support agent"
          />
        </div>
        <div>
          <Label>Description</Label>
          <Input
            value={description}
            maxLength={AGENT_DESCRIPTION_MAX}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Answers customer questions from the handbook."
          />
        </div>
      </div>
    </Modal>
  )
}
