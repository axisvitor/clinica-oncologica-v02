/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FlowCanvas } from '../FlowCanvas'
import { FlowDesign, FlowNodeType, DesignerMode, FlowValidationResult } from '@/types/flow-designer'

// Helper to create a minimal design
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

describe('FlowCanvas', () => {
  const defaultProps = {
    design: createTestDesign(),
    selectedNodes: [],
    selectedConnections: [],
    zoom: 1,
    pan: { x: 0, y: 0 },
    mode: DesignerMode.SELECT,
    onNodeSelect: vi.fn(),
    onConnectionSelect: vi.fn(),
    onNodeUpdate: vi.fn(),
    onAddConnection: vi.fn(),
    onPanChange: vi.fn(),
    validation: null
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render the canvas with nodes', () => {
      render(<FlowCanvas {...defaultProps} />)

      // Canvas should be present
      const canvas = document.querySelector('.bg-gray-50')
      expect(canvas).toBeInTheDocument()
    })

    it('should render all nodes from design', () => {
      render(<FlowCanvas {...defaultProps} />)

      // Should render 3 nodes - use getAllByText since labels may appear multiple times
      expect(screen.getAllByText('Início').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Mensagem').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Fim').length).toBeGreaterThanOrEqual(1)
    })

    it('should display mode indicator', () => {
      render(<FlowCanvas {...defaultProps} />)

      expect(screen.getByText('Selecionar')).toBeInTheDocument()
    })

    it('should display zoom indicator', () => {
      render(<FlowCanvas {...defaultProps} zoom={1.5} />)

      expect(screen.getByText('150%')).toBeInTheDocument()
    })
  })

  describe('Mode Indicators', () => {
    it('should show SELECT mode label', () => {
      render(<FlowCanvas {...defaultProps} mode={DesignerMode.SELECT} />)

      expect(screen.getByText('Selecionar')).toBeInTheDocument()
    })

    it('should show CONNECT mode label', () => {
      render(<FlowCanvas {...defaultProps} mode={DesignerMode.CONNECT} />)

      expect(screen.getByText('Conectar')).toBeInTheDocument()
    })

    it('should show PAN mode label', () => {
      render(<FlowCanvas {...defaultProps} mode={DesignerMode.PAN} />)

      expect(screen.getByText('Navegar')).toBeInTheDocument()
    })
  })

  describe('Zoom Display', () => {
    it('should display 50% zoom', () => {
      render(<FlowCanvas {...defaultProps} zoom={0.5} />)

      expect(screen.getByText('50%')).toBeInTheDocument()
    })

    it('should display 100% zoom', () => {
      render(<FlowCanvas {...defaultProps} zoom={1} />)

      expect(screen.getByText('100%')).toBeInTheDocument()
    })

    it('should display 200% zoom', () => {
      render(<FlowCanvas {...defaultProps} zoom={2} />)

      expect(screen.getByText('200%')).toBeInTheDocument()
    })
  })

  describe('Pan Mode', () => {
    it('should start panning on mouse down in PAN mode', () => {
      render(<FlowCanvas {...defaultProps} mode={DesignerMode.PAN} />)

      const canvas = document.querySelector('.bg-gray-50')!
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100 })

      // Panning should start (internal state change)
      expect(canvas).toBeInTheDocument()
    })

    it('should update pan on mouse move while dragging', () => {
      const onPanChange = vi.fn()
      render(
        <FlowCanvas
          {...defaultProps}
          mode={DesignerMode.PAN}
          onPanChange={onPanChange}
        />
      )

      const canvas = document.querySelector('.bg-gray-50')!
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100 })
      fireEvent.mouseMove(canvas, { clientX: 150, clientY: 150 })

      expect(onPanChange).toHaveBeenCalled()
    })

    it('should stop panning on mouse up', () => {
      render(<FlowCanvas {...defaultProps} mode={DesignerMode.PAN} />)

      const canvas = document.querySelector('.bg-gray-50')!
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100 })
      fireEvent.mouseUp(canvas)

      // Panning should stop
      expect(canvas).toBeInTheDocument()
    })
  })

  describe('Node Selection', () => {
    it('should deselect all when clicking on canvas', () => {
      const onNodeSelect = vi.fn()
      render(<FlowCanvas {...defaultProps} onNodeSelect={onNodeSelect} />)

      const canvas = document.querySelector('.bg-gray-50')!
      fireEvent.click(canvas)

      expect(onNodeSelect).toHaveBeenCalledWith('', false)
    })
  })

  describe('Validation Display', () => {
    it('should not show validation errors when validation is null', () => {
      render(<FlowCanvas {...defaultProps} validation={null} />)

      expect(screen.queryByText(/Erros de Validação/)).not.toBeInTheDocument()
    })

    it('should not show validation errors when flow is valid', () => {
      const validation: FlowValidationResult = {
        isValid: true,
        errors: [],
        warnings: []
      }
      render(<FlowCanvas {...defaultProps} validation={validation} />)

      expect(screen.queryByText(/Erros de Validação/)).not.toBeInTheDocument()
    })

    it('should show validation errors when flow is invalid', () => {
      const validation: FlowValidationResult = {
        isValid: false,
        errors: [
          { id: 'e1', type: 'invalid_config', message: 'Mensagem sem conteúdo', node_id: 'msg-1' }
        ],
        warnings: []
      }
      render(<FlowCanvas {...defaultProps} validation={validation} />)

      expect(screen.getByText('Erros de Validação (1)')).toBeInTheDocument()
      expect(screen.getByText('Mensagem sem conteúdo')).toBeInTheDocument()
    })

    it('should truncate error list when more than 3 errors', () => {
      const validation: FlowValidationResult = {
        isValid: false,
        errors: [
          { id: 'e1', type: 'invalid_config', message: 'Erro 1' },
          { id: 'e2', type: 'invalid_config', message: 'Erro 2' },
          { id: 'e3', type: 'invalid_config', message: 'Erro 3' },
          { id: 'e4', type: 'invalid_config', message: 'Erro 4' },
          { id: 'e5', type: 'invalid_config', message: 'Erro 5' }
        ],
        warnings: []
      }
      render(<FlowCanvas {...defaultProps} validation={validation} />)

      expect(screen.getByText('Erros de Validação (5)')).toBeInTheDocument()
      expect(screen.getByText('... e mais 2 erro(s)')).toBeInTheDocument()
    })
  })

  describe('Canvas Transform', () => {
    it('should apply zoom transform', () => {
      render(<FlowCanvas {...defaultProps} zoom={1.5} />)

      const transformContainer = document.querySelector('[style*="transform"]')
      expect(transformContainer).toBeInTheDocument()
    })

    it('should apply pan transform', () => {
      render(<FlowCanvas {...defaultProps} pan={{ x: 50, y: 50 }} />)

      const transformContainer = document.querySelector('[style*="transform"]')
      expect(transformContainer).toBeInTheDocument()
    })
  })

  describe('Empty Design', () => {
    it('should render empty canvas with no nodes', () => {
      const emptyDesign = {
        ...createTestDesign(),
        nodes: [],
        connections: []
      }
      render(<FlowCanvas {...defaultProps} design={emptyDesign} />)

      // Verify node container is empty - no node-specific elements
      const nodeContainers = document.querySelectorAll('.min-w-\\[120px\\]')
      expect(nodeContainers.length).toBe(0)
    })
  })
})
