/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PropertyPanel } from '../PropertyPanel'
import { FlowDesign, FlowNodeType, FlowValidationResult } from '@/types/flow-designer'

// Helper to create a test design
function createTestDesign(): FlowDesign {
  return {
    id: 'test-design',
    name: 'Test Flow',
    description: 'A test flow',
    version: '1.0.0',
    nodes: [
      {
        id: 'start-1',
        type: FlowNodeType.START,
        position: { x: 100, y: 100 },
        data: { label: 'Início', description: 'Start point', config: {} },
      },
      {
        id: 'msg-1',
        type: FlowNodeType.MESSAGE,
        position: { x: 100, y: 200 },
        data: { label: 'Mensagem', config: { content: 'Olá!' } },
      },
      {
        id: 'cond-1',
        type: FlowNodeType.CONDITION,
        position: { x: 100, y: 300 },
        data: { label: 'Condição', config: { operator: 'AND' } },
      },
      {
        id: 'delay-1',
        type: FlowNodeType.DELAY,
        position: { x: 100, y: 400 },
        data: { label: 'Atraso', config: { duration: 5, unit: 'minutes' } },
      },
      {
        id: 'action-1',
        type: FlowNodeType.ACTION,
        position: { x: 100, y: 500 },
        data: { label: 'Ação', config: { action_type: 'set_variable' } },
      },
      {
        id: 'ai-1',
        type: FlowNodeType.AI_RESPONSE,
        position: { x: 100, y: 600 },
        data: {
          label: 'IA',
          config: { prompt_template: 'Test prompt', fallback_message: 'Fallback' },
        },
      },
      {
        id: 'end-1',
        type: FlowNodeType.END,
        position: { x: 100, y: 700 },
        data: { label: 'Fim', config: {} },
      },
    ],
    connections: [
      { id: 'c1', source: 'start-1', target: 'msg-1', label: 'Continue' },
      { id: 'c2', source: 'msg-1', target: 'end-1', condition: "response == 'yes'" },
    ],
    variables: [],
    metadata: {
      author: 'test',
      tags: [],
      category: 'test',
      complexity_level: 'simple',
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}

describe('PropertyPanel', () => {
  const defaultProps = {
    design: createTestDesign(),
    selectedNodes: [],
    selectedConnections: [],
    onUpdateNode: vi.fn(),
    validation: null,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Empty State', () => {
    it('should show empty state when nothing is selected', () => {
      render(<PropertyPanel {...defaultProps} />)

      expect(screen.getByText('Propriedades')).toBeInTheDocument()
      expect(
        screen.getByText('Selecione um nó ou conexão para editar suas propriedades')
      ).toBeInTheDocument()
    })

    it('should show settings icon in empty state', () => {
      render(<PropertyPanel {...defaultProps} />)

      // Should have Settings icon
      const settingsIcons = document.querySelectorAll('svg')
      expect(settingsIcons.length).toBeGreaterThan(0)
    })
  })

  describe('Node Selection', () => {
    it('should show node properties when a node is selected', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['start-1']} />)

      expect(screen.getByLabelText('Nome do Nó')).toBeInTheDocument()
      expect(screen.getByLabelText('Descrição')).toBeInTheDocument()
      expect(screen.getByText('Tipo')).toBeInTheDocument()
    })

    it('should display node label value', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['start-1']} />)

      const labelInput = screen.getByLabelText('Nome do Nó') as HTMLInputElement
      expect(labelInput.value).toBe('Início')
    })

    it('should display node description value', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['start-1']} />)

      const descriptionInput = screen.getByLabelText('Descrição') as HTMLTextAreaElement
      expect(descriptionInput.value).toBe('Start point')
    })

    it('should display node type badge', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['start-1']} />)

      expect(screen.getByText('START')).toBeInTheDocument()
    })

    it('should display position fields', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['start-1']} />)

      expect(screen.getByLabelText('X')).toBeInTheDocument()
      expect(screen.getByLabelText('Y')).toBeInTheDocument()
    })

    it('should display correct position values', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['start-1']} />)

      const xInput = screen.getByLabelText('X') as HTMLInputElement
      const yInput = screen.getByLabelText('Y') as HTMLInputElement

      expect(xInput.value).toBe('100')
      expect(yInput.value).toBe('100')
    })
  })

  describe('Node Updates', () => {
    it('should call onUpdateNode when label is changed', async () => {
      const onUpdateNode = vi.fn()
      render(
        <PropertyPanel {...defaultProps} selectedNodes={['start-1']} onUpdateNode={onUpdateNode} />
      )

      const labelInput = screen.getByLabelText('Nome do Nó')
      await userEvent.clear(labelInput)
      await userEvent.type(labelInput, 'New Label')

      expect(onUpdateNode).toHaveBeenCalled()
    })

    it('should call onUpdateNode when description is changed', async () => {
      const onUpdateNode = vi.fn()
      render(
        <PropertyPanel {...defaultProps} selectedNodes={['start-1']} onUpdateNode={onUpdateNode} />
      )

      const descriptionInput = screen.getByLabelText('Descrição')
      await userEvent.type(descriptionInput, ' updated')

      expect(onUpdateNode).toHaveBeenCalled()
    })

    it('should call onUpdateNode when X position is changed', async () => {
      const onUpdateNode = vi.fn()
      render(
        <PropertyPanel {...defaultProps} selectedNodes={['start-1']} onUpdateNode={onUpdateNode} />
      )

      const xInput = screen.getByLabelText('X')
      await userEvent.clear(xInput)
      await userEvent.type(xInput, '200')

      expect(onUpdateNode).toHaveBeenCalled()
    })

    it('should call onUpdateNode when Y position is changed', async () => {
      const onUpdateNode = vi.fn()
      render(
        <PropertyPanel {...defaultProps} selectedNodes={['start-1']} onUpdateNode={onUpdateNode} />
      )

      const yInput = screen.getByLabelText('Y')
      await userEvent.clear(yInput)
      await userEvent.type(yInput, '200')

      expect(onUpdateNode).toHaveBeenCalled()
    })
  })

  describe('Message Node Properties', () => {
    it('should show message-specific fields for MESSAGE node', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['msg-1']} />)

      expect(screen.getByLabelText('Conteúdo da Mensagem')).toBeInTheDocument()
      expect(screen.getByLabelText('Tipo de Mensagem')).toBeInTheDocument()
    })

    it('should display message content value', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['msg-1']} />)

      const contentInput = screen.getByLabelText('Conteúdo da Mensagem') as HTMLTextAreaElement
      expect(contentInput.value).toBe('Olá!')
    })

    it('should call onUpdateNode when message content is changed', async () => {
      const onUpdateNode = vi.fn()
      render(
        <PropertyPanel {...defaultProps} selectedNodes={['msg-1']} onUpdateNode={onUpdateNode} />
      )

      const contentInput = screen.getByLabelText('Conteúdo da Mensagem')
      await userEvent.type(contentInput, ' mundo!')

      expect(onUpdateNode).toHaveBeenCalled()
    })
  })

  describe('Condition Node Properties', () => {
    it('should show condition-specific fields for CONDITION node', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['cond-1']} />)

      expect(screen.getByLabelText('Operador')).toBeInTheDocument()
    })
  })

  describe('Delay Node Properties', () => {
    it('should show delay-specific fields for DELAY node', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['delay-1']} />)

      expect(screen.getByLabelText('Duração')).toBeInTheDocument()
      expect(screen.getByLabelText('Unidade')).toBeInTheDocument()
    })

    it('should display delay duration value', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['delay-1']} />)

      const durationInput = screen.getByLabelText('Duração') as HTMLInputElement
      expect(durationInput.value).toBe('5')
    })
  })

  describe('Action Node Properties', () => {
    it('should show action-specific fields for ACTION node', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['action-1']} />)

      expect(screen.getByLabelText('Tipo de Ação')).toBeInTheDocument()
    })
  })

  describe('AI Response Node Properties', () => {
    it('should show AI-specific fields for AI_RESPONSE node', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['ai-1']} />)

      expect(screen.getByLabelText('Template do Prompt')).toBeInTheDocument()
      expect(screen.getByLabelText('Mensagem de Fallback')).toBeInTheDocument()
    })

    it('should display prompt template value', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['ai-1']} />)

      const promptInput = screen.getByLabelText('Template do Prompt') as HTMLTextAreaElement
      expect(promptInput.value).toBe('Test prompt')
    })

    it('should display fallback message value', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['ai-1']} />)

      const fallbackInput = screen.getByLabelText('Mensagem de Fallback') as HTMLInputElement
      expect(fallbackInput.value).toBe('Fallback')
    })
  })

  describe('Connection Selection', () => {
    it('should show connection properties when a connection is selected', () => {
      render(<PropertyPanel {...defaultProps} selectedConnections={['c1']} />)

      expect(screen.getByLabelText('Rótulo da Conexão')).toBeInTheDocument()
      expect(screen.getByLabelText('Condição')).toBeInTheDocument()
    })

    it('should display connection label value', () => {
      render(<PropertyPanel {...defaultProps} selectedConnections={['c1']} />)

      const labelInput = screen.getByLabelText('Rótulo da Conexão') as HTMLInputElement
      expect(labelInput.value).toBe('Continue')
    })

    it('should display connection condition value', () => {
      render(<PropertyPanel {...defaultProps} selectedConnections={['c2']} />)

      const conditionInput = screen.getByLabelText('Condição') as HTMLInputElement
      expect(conditionInput.value).toBe("response == 'yes'")
    })
  })

  describe('Validation Errors', () => {
    it('should show validation errors for selected node', () => {
      const validation: FlowValidationResult = {
        isValid: false,
        errors: [
          { id: 'e1', type: 'invalid_config', message: 'Mensagem sem conteúdo', node_id: 'msg-1' },
        ],
        warnings: [],
      }
      render(<PropertyPanel {...defaultProps} selectedNodes={['msg-1']} validation={validation} />)

      expect(screen.getByText('Erros de Validação')).toBeInTheDocument()
      expect(screen.getByText('• Mensagem sem conteúdo')).toBeInTheDocument()
    })

    it('should show error count badge', () => {
      const validation: FlowValidationResult = {
        isValid: false,
        errors: [
          { id: 'e1', type: 'invalid_config', message: 'Error 1', node_id: 'msg-1' },
          { id: 'e2', type: 'invalid_config', message: 'Error 2', node_id: 'msg-1' },
        ],
        warnings: [],
      }
      render(<PropertyPanel {...defaultProps} selectedNodes={['msg-1']} validation={validation} />)

      expect(screen.getByText('2 erro(s)')).toBeInTheDocument()
    })

    it('should not show errors for other nodes', () => {
      const validation: FlowValidationResult = {
        isValid: false,
        errors: [
          { id: 'e1', type: 'invalid_config', message: 'Mensagem sem conteúdo', node_id: 'msg-1' },
        ],
        warnings: [],
      }
      render(
        <PropertyPanel {...defaultProps} selectedNodes={['start-1']} validation={validation} />
      )

      expect(screen.queryByText('Erros de Validação')).not.toBeInTheDocument()
    })

    it('should not show validation section when no errors', () => {
      const validation: FlowValidationResult = {
        isValid: true,
        errors: [],
        warnings: [],
      }
      render(<PropertyPanel {...defaultProps} selectedNodes={['msg-1']} validation={validation} />)

      expect(screen.queryByText('Erros de Validação')).not.toBeInTheDocument()
    })
  })

  describe('Multi-Selection', () => {
    it('should not show properties when multiple nodes are selected', () => {
      render(<PropertyPanel {...defaultProps} selectedNodes={['start-1', 'msg-1']} />)

      // Should show empty state
      expect(
        screen.getByText('Selecione um nó ou conexão para editar suas propriedades')
      ).toBeInTheDocument()
    })
  })

  describe('Node Priority', () => {
    it('should show node properties over connection properties when both selected', () => {
      render(
        <PropertyPanel {...defaultProps} selectedNodes={['start-1']} selectedConnections={['c1']} />
      )

      // Should show node name field, not connection label
      expect(screen.getByLabelText('Nome do Nó')).toBeInTheDocument()
    })
  })
})
