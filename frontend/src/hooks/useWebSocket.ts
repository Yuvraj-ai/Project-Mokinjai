import { useEffect, useRef, useCallback } from 'react'
import { useExecutionStore } from '../store/executionStore'
import type { NodeExecutionStatus } from '../store/executionStore'

interface WebSocketMessage {
  type: 'execution_started' | 'node_status' | 'execution_completed' | 'execution_failed' | 'error'
  executionId?: string
  nodeId?: string
  status?: NodeExecutionStatus
  output?: Record<string, unknown>
  error?: string
}

interface UseWebSocketOptions {
  executionId: string | null
  onMessage?: (message: WebSocketMessage) => void
  onError?: (error: Event) => void
  onClose?: () => void
}

export function useWebSocket({
  executionId,
  onMessage,
  onError,
  onClose,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const { updateExecution, updateNodeStatus, completeExecution } =
    useExecutionStore()

  const connect = useCallback(() => {
    if (!executionId) return

    // Determine WebSocket URL based on current location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/executions/${executionId}`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      // Connection established
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)

        switch (message.type) {
          case 'execution_started':
            updateExecution({ status: 'running' })
            break

          case 'node_status':
            if (message.nodeId && message.status) {
              updateNodeStatus(message.nodeId, message.status)
            }
            break

          case 'execution_completed':
            completeExecution(message.output)
            break

          case 'execution_failed':
            completeExecution(undefined, message.error ?? 'Execution failed')
            break

          case 'error':
            // Server-side error
            break
        }

        onMessage?.(message)
      } catch {
        // Failed to parse message
      }
    }

    ws.onerror = (event) => {
      onError?.(event)
    }

    ws.onclose = () => {
      wsRef.current = null
      onClose?.()
    }

    wsRef.current = ws
  }, [executionId, updateExecution, updateNodeStatus, completeExecution, onMessage, onError, onClose])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  // Auto-connect when executionId changes
  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    send,
    disconnect,
    reconnect: connect,
  }
}
