/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NodePalette } from '../NodePalette'
import { FlowNodeType } from '@/lib/types/flow-designer'

describe('NodePalette', () => {
  const defaultProps = {
    onAddNode: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render the palette with title', () => {
      render(<NodePalette {...defaultProps} />)

      expect(screen.getByText('Componentes')).toBeInTheDocument()
    })

    it('should render all node types', () => {
      render(<NodePalette {...defaultProps} />)

      expect(screen.getByText('Início')).toBeInTheDocument()
      expect(screen.getByText('Mensagem')).toBeInTheDocument()
      expect(screen.getByText('Condição')).toBeInTheDocument()
      expect(screen.getByText('Atraso')).toBeInTheDocument()
      expect(screen.getByText('Ação')).toBeInTheDocument()
      expect(screen.getByText('Resposta IA')).toBeInTheDocument()
      expect(screen.getByText('Quiz')).toBeInTheDocument()
      expect(screen.getByText('Webhook')).toBeInTheDocument()
      expect(screen.getByText('Fim')).toBeInTheDocument()
    })

    it('should render node descriptions', () => {
      render(<NodePalette {...defaultProps} />)

      expect(screen.getByText('Ponto de entrada do fluxo')).toBeInTheDocument()
      expect(screen.getByText('Enviar mensagem para o paciente')).toBeInTheDocument()
      expect(screen.getByText('Decisão baseada em condições')).toBeInTheDocument()
      expect(screen.getByText('Aguardar por um período')).toBeInTheDocument()
      expect(screen.getByText('Executar uma ação específica')).toBeInTheDocument()
      expect(screen.getByText('Gerar resposta com IA')).toBeInTheDocument()
      expect(screen.getByText('Questionário para o paciente')).toBeInTheDocument()
      expect(screen.getByText('Chamar API externa')).toBeInTheDocument()
      expect(screen.getByText('Finalizar o fluxo')).toBeInTheDocument()
    })

    it('should render usage instructions', () => {
      render(<NodePalette {...defaultProps} />)

      expect(screen.getByText('Como usar:')).toBeInTheDocument()
      expect(screen.getByText('• Clique para adicionar ao canvas')).toBeInTheDocument()
      expect(screen.getByText('• Arraste para posicionar')).toBeInTheDocument()
      expect(screen.getByText('• Use modo "Conectar" para ligar nós')).toBeInTheDocument()
    })

    it('should render quick templates section', () => {
      render(<NodePalette {...defaultProps} />)

      expect(screen.getByText('Templates Rápidos')).toBeInTheDocument()
      expect(screen.getByText('Fluxo Simples')).toBeInTheDocument()
      expect(screen.getByText('Fluxo Condicional')).toBeInTheDocument()
      expect(screen.getByText('Fluxo com IA')).toBeInTheDocument()
    })
  })

  describe('Node Type Buttons', () => {
    it('should call onAddNode when clicking START node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const startButton = screen.getByText('Início').closest('button')!
      await userEvent.click(startButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.START, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking MESSAGE node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const messageButton = screen.getByText('Mensagem').closest('button')!
      await userEvent.click(messageButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.MESSAGE, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking CONDITION node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const conditionButton = screen.getByText('Condição').closest('button')!
      await userEvent.click(conditionButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.CONDITION, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking DELAY node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const delayButton = screen.getByText('Atraso').closest('button')!
      await userEvent.click(delayButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.DELAY, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking ACTION node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const actionButton = screen.getByText('Ação').closest('button')!
      await userEvent.click(actionButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.ACTION, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking AI_RESPONSE node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const aiButton = screen.getByText('Resposta IA').closest('button')!
      await userEvent.click(aiButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.AI_RESPONSE, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking QUIZ node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const quizButton = screen.getByText('Quiz').closest('button')!
      await userEvent.click(quizButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.QUIZ, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking WEBHOOK node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const webhookButton = screen.getByText('Webhook').closest('button')!
      await userEvent.click(webhookButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.WEBHOOK, { x: 300, y: 200 })
    })

    it('should call onAddNode when clicking END node', async () => {
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const endButton = screen.getByText('Fim').closest('button')!
      await userEvent.click(endButton)

      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.END, { x: 300, y: 200 })
    })
  })

  describe('Drag and Drop', () => {
    it('should set drag data when dragging starts', () => {
      render(<NodePalette {...defaultProps} />)

      const button = screen.getByText('Início').closest('button')!

      const mockDataTransfer = {
        setData: vi.fn(),
        effectAllowed: ''
      }

      fireEvent.dragStart(button, { dataTransfer: mockDataTransfer })

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('application/node-type', FlowNodeType.START)
      expect(mockDataTransfer.effectAllowed).toBe('copy')
    })

    it('should have draggable attribute on buttons', () => {
      render(<NodePalette {...defaultProps} />)

      const buttons = screen.getAllByRole('button').slice(0, 9) // First 9 are node type buttons
      buttons.forEach(button => {
        expect(button).toHaveAttribute('draggable', 'true')
      })
    })
  })

  describe('Quick Templates', () => {
    it('should add simple flow when clicking "Fluxo Simples"', async () => {
      vi.useFakeTimers()
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const simpleFlowButton = screen.getByText('Fluxo Simples')
      await userEvent.click(simpleFlowButton)

      // First call is immediate
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.START, { x: 100, y: 100 })

      // Fast forward timers for delayed calls
      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.MESSAGE, { x: 100, y: 200 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.END, { x: 100, y: 300 })

      vi.useRealTimers()
    })

    it('should add conditional flow when clicking "Fluxo Condicional"', async () => {
      vi.useFakeTimers()
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const conditionalFlowButton = screen.getByText('Fluxo Condicional')
      await userEvent.click(conditionalFlowButton)

      // First call is immediate
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.START, { x: 100, y: 100 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.MESSAGE, { x: 100, y: 200 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.CONDITION, { x: 100, y: 300 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.MESSAGE, { x: 50, y: 400 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.MESSAGE, { x: 150, y: 400 })

      vi.useRealTimers()
    })

    it('should add AI flow when clicking "Fluxo com IA"', async () => {
      vi.useFakeTimers()
      const onAddNode = vi.fn()
      render(<NodePalette onAddNode={onAddNode} />)

      const aiFlowButton = screen.getByText('Fluxo com IA')
      await userEvent.click(aiFlowButton)

      // First call is immediate
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.START, { x: 100, y: 100 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.MESSAGE, { x: 100, y: 200 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.AI_RESPONSE, { x: 100, y: 300 })

      vi.advanceTimersByTime(100)
      expect(onAddNode).toHaveBeenCalledWith(FlowNodeType.END, { x: 100, y: 400 })

      vi.useRealTimers()
    })
  })

  describe('Styling', () => {
    it('should have card structure', () => {
      render(<NodePalette {...defaultProps} />)

      // Should have card header with title
      expect(screen.getByText('Componentes')).toBeInTheDocument()
    })

    it('should render node type buttons with ghost variant', () => {
      render(<NodePalette {...defaultProps} />)

      const buttons = screen.getAllByRole('button')
      // Node type buttons should have ghost styling
      buttons.slice(0, 9).forEach(button => {
        expect(button).toHaveClass('justify-start')
      })
    })

    it('should render template buttons with outline variant', () => {
      render(<NodePalette {...defaultProps} />)

      const templateButtons = [
        screen.getByText('Fluxo Simples'),
        screen.getByText('Fluxo Condicional'),
        screen.getByText('Fluxo com IA')
      ]

      templateButtons.forEach(button => {
        expect(button).toBeInTheDocument()
      })
    })
  })

  describe('Icons', () => {
    it('should render icons for each node type', () => {
      render(<NodePalette {...defaultProps} />)

      // Check that SVG icons are present within buttons
      const buttons = screen.getAllByRole('button').slice(0, 9)
      buttons.forEach(button => {
        const svg = button.querySelector('svg')
        expect(svg).toBeInTheDocument()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have accessible button labels', () => {
      render(<NodePalette {...defaultProps} />)

      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThan(0)
    })
  })
})
