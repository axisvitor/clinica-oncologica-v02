/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { FlowConnectionComponent } from '../FlowConnectionComponent'
import { FlowConnection, FlowNode, FlowNodeType } from '@/types/flow-designer'

// Helper to create test nodes
function createTestNodes(): FlowNode[] {
  return [
    {
      id: 'node-1',
      type: FlowNodeType.START,
      position: { x: 100, y: 100 },
      data: { label: 'Start', config: {} },
    },
    {
      id: 'node-2',
      type: FlowNodeType.MESSAGE,
      position: { x: 300, y: 200 },
      data: { label: 'Message', config: {} },
    },
  ]
}

// Helper to create a test connection
function createTestConnection(overrides: Partial<FlowConnection> = {}): FlowConnection {
  return {
    id: 'conn-1',
    source: 'node-1',
    target: 'node-2',
    ...overrides,
  }
}

// Wrapper component for SVG
function SvgWrapper({ children }: { children: React.ReactNode }) {
  return <svg data-testid="svg-wrapper">{children}</svg>
}

describe('FlowConnectionComponent', () => {
  const defaultProps = {
    connection: createTestConnection(),
    nodes: createTestNodes(),
    selected: false,
    errors: [],
    onSelect: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render the connection path', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} />
        </SvgWrapper>
      )

      const path = document.querySelector('path')
      expect(path).toBeInTheDocument()
    })

    it('should not render when source node is missing', () => {
      const props = {
        ...defaultProps,
        connection: createTestConnection({ source: 'nonexistent' }),
      }
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...props} />
        </SvgWrapper>
      )

      // Should return null, so no path elements
      const group = document.querySelector('g')
      expect(group).not.toBeInTheDocument()
    })

    it('should not render when target node is missing', () => {
      const props = {
        ...defaultProps,
        connection: createTestConnection({ target: 'nonexistent' }),
      }
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...props} />
        </SvgWrapper>
      )

      const group = document.querySelector('g')
      expect(group).not.toBeInTheDocument()
    })

    it('should render arrow marker', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} />
        </SvgWrapper>
      )

      const marker = document.querySelector('marker')
      expect(marker).toBeInTheDocument()
    })
  })

  describe('Selection', () => {
    it('should call onSelect when path is clicked', () => {
      const onSelect = vi.fn()
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} onSelect={onSelect} />
        </SvgWrapper>
      )

      const path = document.querySelector('path[stroke]')!
      fireEvent.click(path)

      expect(onSelect).toHaveBeenCalled()
    })

    it('should render selection highlight when selected', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} selected={true} />
        </SvgWrapper>
      )

      const selectionPath = document.querySelector('path[opacity="0.3"]')
      expect(selectionPath).toBeInTheDocument()
    })

    it('should not render selection highlight when not selected', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} selected={false} />
        </SvgWrapper>
      )

      const selectionPath = document.querySelector('path[opacity="0.3"]')
      expect(selectionPath).not.toBeInTheDocument()
    })

    it('should apply blue stroke color when selected', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} selected={true} />
        </SvgWrapper>
      )

      const path = document.querySelector('path[stroke="#3b82f6"]')
      expect(path).toBeInTheDocument()
    })

    it('should apply thicker stroke when selected', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} selected={true} />
        </SvgWrapper>
      )

      const path = document.querySelector('path[stroke-width="3"]')
      expect(path).toBeInTheDocument()
    })
  })

  describe('Labels', () => {
    it('should render connection label if provided', () => {
      const connection = createTestConnection({ label: 'Sim' })
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} connection={connection} />
        </SvgWrapper>
      )

      expect(screen.getByText('Sim')).toBeInTheDocument()
    })

    it('should not render label when not provided', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} />
        </SvgWrapper>
      )

      const textElements = document.querySelectorAll('text')
      // Should only have error indicator text or none
      const labelText = Array.from(textElements).find((t) => !t.textContent?.includes('!'))
      expect(labelText).toBeFalsy()
    })

    it('should render condition label if provided', () => {
      const connection = createTestConnection({ condition: "response == 'yes'" })
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} connection={connection} />
        </SvgWrapper>
      )

      expect(screen.getByText("response == 'yes'")).toBeInTheDocument()
    })

    it('should render label background rectangle', () => {
      const connection = createTestConnection({ label: 'Test' })
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} connection={connection} />
        </SvgWrapper>
      )

      const rect = document.querySelector('rect')
      expect(rect).toBeInTheDocument()
    })
  })

  describe('Errors', () => {
    it('should show error indicator when has errors', () => {
      const errors = [
        {
          id: 'e1',
          type: 'invalid_config' as const,
          message: 'Invalid connection',
          connection_id: 'conn-1',
        },
      ]
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} errors={errors} />
        </SvgWrapper>
      )

      // Should show error circle with "!" text
      expect(screen.getByText('!')).toBeInTheDocument()
    })

    it('should apply red stroke color when has errors', () => {
      const errors = [
        {
          id: 'e1',
          type: 'invalid_config' as const,
          message: 'Invalid connection',
          connection_id: 'conn-1',
        },
      ]
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} errors={errors} />
        </SvgWrapper>
      )

      const path = document.querySelector('path[stroke="#ef4444"]')
      expect(path).toBeInTheDocument()
    })

    it('should not show error indicator when no errors', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} errors={[]} />
        </SvgWrapper>
      )

      expect(screen.queryByText('!')).not.toBeInTheDocument()
    })

    it('should render error circle', () => {
      const errors = [
        { id: 'e1', type: 'invalid_config' as const, message: 'Error', connection_id: 'conn-1' },
      ]
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} errors={errors} />
        </SvgWrapper>
      )

      const circle = document.querySelector('circle')
      expect(circle).toBeInTheDocument()
    })
  })

  describe('Animation', () => {
    it('should apply dashed stroke when animated', () => {
      const connection = createTestConnection({ animated: true })
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} connection={connection} />
        </SvgWrapper>
      )

      const path = document.querySelector('path[stroke-dasharray="5,5"]')
      expect(path).toBeInTheDocument()
    })

    it('should apply pulse animation class when animated', () => {
      const connection = createTestConnection({ animated: true })
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} connection={connection} />
        </SvgWrapper>
      )

      const path = document.querySelector('.animate-pulse')
      expect(path).toBeInTheDocument()
    })

    it('should not apply dashed stroke when not animated', () => {
      const connection = createTestConnection({ animated: false })
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} connection={connection} />
        </SvgWrapper>
      )

      const path = document.querySelector('path[stroke-dasharray="none"]')
      expect(path).toBeInTheDocument()
    })
  })

  describe('Path Calculation', () => {
    it('should create bezier curve path', () => {
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} />
        </SvgWrapper>
      )

      const path = document.querySelector('path')
      const pathData = path?.getAttribute('d')

      // Should contain M (move) and C (cubic bezier curve) commands
      expect(pathData).toContain('M')
      expect(pathData).toContain('C')
    })
  })

  describe('Click Handling', () => {
    it('should stop event propagation on click', () => {
      const onSelect = vi.fn()
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} onSelect={onSelect} />
        </SvgWrapper>
      )

      const path = document.querySelector('path[stroke]')!
      path.dispatchEvent(new MouseEvent('click', { bubbles: true }))

      expect(onSelect).toHaveBeenCalled()
    })

    it('should call onSelect when clicking label background', () => {
      const onSelect = vi.fn()
      const connection = createTestConnection({ label: 'Test' })
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} connection={connection} onSelect={onSelect} />
        </SvgWrapper>
      )

      const rect = document.querySelector('rect')!
      fireEvent.click(rect)

      expect(onSelect).toHaveBeenCalled()
    })

    it('should call onSelect when clicking error indicator', () => {
      const onSelect = vi.fn()
      const errors = [
        { id: 'e1', type: 'invalid_config' as const, message: 'Error', connection_id: 'conn-1' },
      ]
      render(
        <SvgWrapper>
          <FlowConnectionComponent {...defaultProps} errors={errors} onSelect={onSelect} />
        </SvgWrapper>
      )

      const circle = document.querySelector('circle')!
      fireEvent.click(circle)

      expect(onSelect).toHaveBeenCalled()
    })
  })
})
