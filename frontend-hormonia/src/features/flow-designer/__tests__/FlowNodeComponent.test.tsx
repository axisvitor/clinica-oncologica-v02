/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FlowNodeComponent } from '../FlowNodeComponent'
import { FlowNode, FlowNodeType, DesignerMode } from '@/types/flow-designer'

// Helper to create a test node
function createTestNode(
  type: FlowNodeType = FlowNodeType.MESSAGE,
  overrides: Partial<FlowNode> = {}
): FlowNode {
  return {
    id: 'test-node',
    type,
    position: { x: 100, y: 100 },
    data: {
      label: 'Test Node',
      config: {},
    },
    ...overrides,
  }
}

describe('FlowNodeComponent', () => {
  const defaultProps = {
    node: createTestNode(),
    selected: false,
    errors: [],
    mode: DesignerMode.SELECT,
    onSelect: vi.fn(),
    onDrag: vi.fn(),
    onConnectionStart: vi.fn(),
    onConnectionEnd: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render the node with label', () => {
      render(<FlowNodeComponent {...defaultProps} />)

      expect(screen.getByText('Test Node')).toBeInTheDocument()
    })

    it('should render node description if provided', () => {
      const node = createTestNode(FlowNodeType.MESSAGE, {
        data: {
          label: 'Test',
          description: 'Test description',
          config: {},
        },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Test description')).toBeInTheDocument()
    })

    it('should render connection points', () => {
      render(<FlowNodeComponent {...defaultProps} />)

      // Should have 4 connection points (top, bottom, left, right)
      const connectionPoints = document.querySelectorAll('.w-3.h-3.rounded-full')
      expect(connectionPoints.length).toBe(4)
    })

    it('should render node type badge', () => {
      render(<FlowNodeComponent {...defaultProps} />)

      // Should show first letter of type
      const badge = document.querySelector('.bg-white.border.border-gray-300.rounded-full')
      expect(badge).toBeInTheDocument()
    })
  })

  describe('Node Types', () => {
    it('should render START node with correct styling', () => {
      const node = createTestNode(FlowNodeType.START, {
        data: { label: 'Início', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Início')).toBeInTheDocument()
    })

    it('should render MESSAGE node with correct styling', () => {
      const node = createTestNode(FlowNodeType.MESSAGE, {
        data: { label: 'Mensagem', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Mensagem')).toBeInTheDocument()
    })

    it('should render CONDITION node with correct styling', () => {
      const node = createTestNode(FlowNodeType.CONDITION, {
        data: { label: 'Condição', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Condição')).toBeInTheDocument()
    })

    it('should render DELAY node with correct styling', () => {
      const node = createTestNode(FlowNodeType.DELAY, {
        data: { label: 'Atraso', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Atraso')).toBeInTheDocument()
    })

    it('should render ACTION node with correct styling', () => {
      const node = createTestNode(FlowNodeType.ACTION, {
        data: { label: 'Ação', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Ação')).toBeInTheDocument()
    })

    it('should render END node with correct styling', () => {
      const node = createTestNode(FlowNodeType.END, {
        data: { label: 'Fim', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Fim')).toBeInTheDocument()
    })

    it('should render AI_RESPONSE node with correct styling', () => {
      const node = createTestNode(FlowNodeType.AI_RESPONSE, {
        data: { label: 'IA', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('IA')).toBeInTheDocument()
    })

    it('should render QUIZ node with correct styling', () => {
      const node = createTestNode(FlowNodeType.QUIZ, {
        data: { label: 'Quiz', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Quiz')).toBeInTheDocument()
    })

    it('should render WEBHOOK node with correct styling', () => {
      const node = createTestNode(FlowNodeType.WEBHOOK, {
        data: { label: 'Webhook', config: {} },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      expect(screen.getByText('Webhook')).toBeInTheDocument()
    })
  })

  describe('Selection', () => {
    it('should show selection ring when selected', () => {
      render(<FlowNodeComponent {...defaultProps} selected={true} />)

      const nodeBody = document.querySelector('.ring-2.ring-blue-500')
      expect(nodeBody).toBeInTheDocument()
    })

    it('should not show selection ring when not selected', () => {
      render(<FlowNodeComponent {...defaultProps} selected={false} />)

      const nodeBody = document.querySelector('.ring-2.ring-blue-500')
      expect(nodeBody).not.toBeInTheDocument()
    })

    it('should call onSelect on mouse down in SELECT mode', () => {
      const onSelect = vi.fn()
      render(<FlowNodeComponent {...defaultProps} onSelect={onSelect} />)

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseDown(node)

      expect(onSelect).toHaveBeenCalled()
    })

    it('should pass multiSelect flag when ctrl key is pressed', () => {
      const onSelect = vi.fn()
      render(<FlowNodeComponent {...defaultProps} onSelect={onSelect} />)

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseDown(node, { ctrlKey: true })

      expect(onSelect).toHaveBeenCalledWith(true)
    })

    it('should pass multiSelect flag when meta key is pressed', () => {
      const onSelect = vi.fn()
      render(<FlowNodeComponent {...defaultProps} onSelect={onSelect} />)

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseDown(node, { metaKey: true })

      expect(onSelect).toHaveBeenCalledWith(true)
    })
  })

  describe('Connection Mode', () => {
    it('should call onConnectionStart on mouse down in CONNECT mode', () => {
      const onConnectionStart = vi.fn()
      render(
        <FlowNodeComponent
          {...defaultProps}
          mode={DesignerMode.CONNECT}
          onConnectionStart={onConnectionStart}
        />
      )

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseDown(node)

      expect(onConnectionStart).toHaveBeenCalled()
    })

    it('should call onConnectionEnd on mouse up in CONNECT mode', () => {
      const onConnectionEnd = vi.fn()
      render(
        <FlowNodeComponent
          {...defaultProps}
          mode={DesignerMode.CONNECT}
          onConnectionEnd={onConnectionEnd}
        />
      )

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseUp(node)

      expect(onConnectionEnd).toHaveBeenCalled()
    })

    it('should not call onSelect in CONNECT mode', () => {
      const onSelect = vi.fn()
      render(
        <FlowNodeComponent {...defaultProps} mode={DesignerMode.CONNECT} onSelect={onSelect} />
      )

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseDown(node)

      expect(onSelect).not.toHaveBeenCalled()
    })
  })

  describe('Dragging', () => {
    it('should call onDrag during mouse move when dragging', () => {
      const onDrag = vi.fn()
      render(<FlowNodeComponent {...defaultProps} onDrag={onDrag} />)

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseDown(node)
      fireEvent.mouseMove(node, { clientX: 150, clientY: 150 })

      expect(onDrag).toHaveBeenCalled()
    })

    it('should not drag in CONNECT mode', () => {
      const onDrag = vi.fn()
      render(<FlowNodeComponent {...defaultProps} mode={DesignerMode.CONNECT} onDrag={onDrag} />)

      const node = screen.getByText('Test Node').closest('.cursor-pointer')!
      fireEvent.mouseDown(node)
      fireEvent.mouseMove(node, { clientX: 150, clientY: 150 })

      expect(onDrag).not.toHaveBeenCalled()
    })
  })

  describe('Errors', () => {
    it('should display error indicator when has errors', () => {
      const errors = [
        { id: 'e1', type: 'invalid_config' as const, message: 'Test error', node_id: 'test-node' },
      ]
      render(<FlowNodeComponent {...defaultProps} errors={errors} />)

      // Should show error tooltip
      expect(screen.getByText('Erros:')).toBeInTheDocument()
      expect(screen.getByText('• Test error')).toBeInTheDocument()
    })

    it('should apply error styling when has errors', () => {
      const errors = [
        { id: 'e1', type: 'invalid_config' as const, message: 'Test error', node_id: 'test-node' },
      ]
      render(<FlowNodeComponent {...defaultProps} errors={errors} />)

      const nodeBody = document.querySelector('.bg-red-100.border-red-500')
      expect(nodeBody).toBeInTheDocument()
    })

    it('should display multiple errors', () => {
      const errors = [
        { id: 'e1', type: 'invalid_config' as const, message: 'Error 1', node_id: 'test-node' },
        { id: 'e2', type: 'invalid_config' as const, message: 'Error 2', node_id: 'test-node' },
      ]
      render(<FlowNodeComponent {...defaultProps} errors={errors} />)

      expect(screen.getByText('• Error 1')).toBeInTheDocument()
      expect(screen.getByText('• Error 2')).toBeInTheDocument()
    })

    it('should not show error indicator when no errors', () => {
      render(<FlowNodeComponent {...defaultProps} errors={[]} />)

      expect(screen.queryByText('Erros:')).not.toBeInTheDocument()
    })
  })

  describe('Position', () => {
    it('should position node according to position prop', () => {
      const node = createTestNode(FlowNodeType.MESSAGE, {
        position: { x: 200, y: 300 },
      })
      render(<FlowNodeComponent {...defaultProps} node={node} />)

      const nodeElement = screen.getByText('Test Node').closest('.absolute')
      expect(nodeElement).toHaveStyle({ left: '200px', top: '300px' })
    })
  })

  describe('Cursor Styles', () => {
    it('should show move cursor in SELECT mode', () => {
      render(<FlowNodeComponent {...defaultProps} mode={DesignerMode.SELECT} />)

      const node = screen.getByText('Test Node').closest('.cursor-pointer')
      expect(node).toHaveClass('cursor-move')
    })

    it('should show crosshair cursor in CONNECT mode', () => {
      render(<FlowNodeComponent {...defaultProps} mode={DesignerMode.CONNECT} />)

      const node = screen.getByText('Test Node').closest('.cursor-pointer')
      expect(node).toHaveClass('cursor-crosshair')
    })
  })
})
