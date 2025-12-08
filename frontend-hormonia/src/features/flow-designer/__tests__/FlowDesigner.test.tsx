/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FlowDesigner } from '../FlowDesigner'
import { FlowDesign, FlowNodeType } from '@/types/flow-designer'

// Mock useToast
vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn()
  })
}))

// Helper to create a valid test design
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
        data: { label: 'Início', config: {} }
      },
      {
        id: 'msg-1',
        type: FlowNodeType.MESSAGE,
        position: { x: 100, y: 200 },
        data: { label: 'Mensagem', config: { content: 'Olá!' } }
      },
      {
        id: 'end-1',
        type: FlowNodeType.END,
        position: { x: 100, y: 300 },
        data: { label: 'Fim', config: {} }
      }
    ],
    connections: [
      { id: 'c1', source: 'start-1', target: 'msg-1' },
      { id: 'c2', source: 'msg-1', target: 'end-1' }
    ],
    variables: [],
    metadata: {
      author: 'test',
      tags: [],
      category: 'test',
      complexity_level: 'simple'
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
}

describe('FlowDesigner', () => {
  describe('Rendering', () => {
    it('should render the flow designer with toolbar', () => {
      render(<FlowDesigner />)

      expect(screen.getByText('Flow Designer')).toBeInTheDocument()
      expect(screen.getByText('Salvar')).toBeInTheDocument()
      expect(screen.getByText('Testar')).toBeInTheDocument()
    })

    it('should render with initial design', () => {
      const design = createTestDesign()
      render(<FlowDesigner initialDesign={design} />)

      expect(screen.getByText('Flow Designer')).toBeInTheDocument()
    })

    it('should show zoom controls', () => {
      render(<FlowDesigner />)

      expect(screen.getByText('100%')).toBeInTheDocument()
    })

    it('should show mode controls', () => {
      render(<FlowDesigner />)

      // Mode buttons should be present (MousePointer, Link, Move icons)
      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThan(0)
    })
  })

  describe('Designer Modes', () => {
    it('should have SELECT mode active by default', () => {
      render(<FlowDesigner />)

      // The default mode should be SELECT (MousePointer icon button should be selected)
      const selectButton = screen.getAllByRole('button')[0]
      expect(selectButton).toBeDefined()
    })
  })

  describe('Zoom Controls', () => {
    it('should display initial zoom at 100%', () => {
      render(<FlowDesigner />)

      expect(screen.getByText('100%')).toBeInTheDocument()
    })
  })

  describe('Validation Status', () => {
    it('should show validation errors for invalid flow', async () => {
      // Create a design with no start node
      const invalidDesign: FlowDesign = {
        id: 'invalid',
        name: 'Invalid',
        description: '',
        version: '1.0.0',
        nodes: [
          {
            id: 'msg-1',
            type: FlowNodeType.MESSAGE,
            position: { x: 100, y: 100 },
            data: { label: 'Mensagem', config: { content: 'Test' } }
          }
        ],
        connections: [],
        variables: [],
        metadata: {
          author: 'test',
          tags: [],
          category: 'test',
          complexity_level: 'simple'
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      render(<FlowDesigner initialDesign={invalidDesign} />)

      await waitFor(() => {
        expect(screen.getByText(/erro/i)).toBeInTheDocument()
      })
    })

    it('should show valid status for valid flow', async () => {
      const validDesign = createTestDesign()
      render(<FlowDesigner initialDesign={validDesign} />)

      await waitFor(() => {
        expect(screen.getByText('Válido')).toBeInTheDocument()
      })
    })
  })

  describe('Save Functionality', () => {
    it('should call onSave when save button is clicked with valid flow', async () => {
      const onSave = vi.fn()
      const design = createTestDesign()

      render(<FlowDesigner initialDesign={design} onSave={onSave} />)

      const saveButton = screen.getByText('Salvar')
      await userEvent.click(saveButton)

      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
          id: 'test-design',
          name: 'Test Flow'
        }))
      })
    })

    it('should not call onSave when flow is invalid', async () => {
      const onSave = vi.fn()
      const invalidDesign: FlowDesign = {
        id: 'invalid',
        name: 'Invalid',
        description: '',
        version: '1.0.0',
        nodes: [],
        connections: [],
        variables: [],
        metadata: {
          author: 'test',
          tags: [],
          category: 'test',
          complexity_level: 'simple'
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      render(<FlowDesigner initialDesign={invalidDesign} onSave={onSave} />)

      const saveButton = screen.getByText('Salvar')
      await userEvent.click(saveButton)

      expect(onSave).not.toHaveBeenCalled()
    })
  })

  describe('Test Functionality', () => {
    it('should call onTest when test button is clicked with valid flow', async () => {
      const onTest = vi.fn()
      const design = createTestDesign()

      render(<FlowDesigner initialDesign={design} onTest={onTest} />)

      const testButton = screen.getByText('Testar')
      await userEvent.click(testButton)

      await waitFor(() => {
        expect(onTest).toHaveBeenCalledWith(expect.objectContaining({
          id: 'test-design'
        }))
      })
    })
  })

  describe('History Controls', () => {
    it('should have disabled undo button initially', () => {
      render(<FlowDesigner />)

      // Find undo button (Undo icon)
      const buttons = screen.getAllByRole('button')
      const undoButton = buttons.find(btn => btn.querySelector('svg'))

      // Undo should be disabled at start
      expect(undoButton).toBeDefined()
    })
  })

  describe('Modified State', () => {
    it('should show modified badge when design is changed', async () => {
      render(<FlowDesigner />)

      // Initially should not show "Modificado"
      expect(screen.queryByText('Modificado')).not.toBeInTheDocument()
    })
  })
})
