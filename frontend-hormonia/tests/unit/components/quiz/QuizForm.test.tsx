import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QuizForm } from '@/components/quiz/QuizForm'

// Mock API client
const mockSubmitResponse = vi.fn()
vi.mock('../../lib/api-client', () => ({
  apiClient: {
    quiz: {
      submitResponse: mockSubmitResponse,
    },
  },
}))

// Mock UI components
vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, disabled, size }: any) => (
    <button
      data-testid="submit-button"
      onClick={onClick}
      disabled={disabled}
      data-size={size}
    >
      {children}
    </button>
  ),
}))

vi.mock('@/components/ui/card', () => ({
  Card: ({ children, className }: any) => (
    <div data-testid="card" className={className}>{children}</div>
  ),
  CardContent: ({ children }: any) => <div data-testid="card-content">{children}</div>,
  CardDescription: ({ children }: any) => <div data-testid="card-description">{children}</div>,
  CardHeader: ({ children }: any) => <div data-testid="card-header">{children}</div>,
  CardTitle: ({ children }: any) => <h3 data-testid="card-title">{children}</h3>,
}))

vi.mock('@/components/ui/radio-group', () => ({
  RadioGroup: ({ children, onValueChange, value }: any) => (
    <div
      data-testid="radio-group"
      data-value={value}
      onClick={() => onValueChange?.('test-value')}
    >
      {children}
    </div>
  ),
  RadioGroupItem: ({ value, id }: any) => (
    <input
      type="radio"
      data-testid={`radio-item-${value}`}
      id={id}
      value={value}
    />
  ),
}))

vi.mock('@/components/ui/checkbox', () => ({
  Checkbox: ({ checked, onCheckedChange, id }: any) => (
    <input
      type="checkbox"
      data-testid={`checkbox-${id}`}
      checked={checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
    />
  ),
}))

vi.mock('@/components/ui/slider', () => ({
  Slider: ({ value, onValueChange, min, max }: any) => (
    <input
      type="range"
      data-testid="slider"
      value={value?.[0] || min}
      min={min}
      max={max}
      onChange={(e) => onValueChange?.([parseInt(e.target.value)])}
    />
  ),
}))

vi.mock('@/components/ui/textarea', () => ({
  Textarea: ({ value, onChange, placeholder }: any) => (
    <textarea
      data-testid="textarea"
      value={value}
      onChange={onChange}
      placeholder={placeholder}
    />
  ),
}))

vi.mock('@/components/ui/label', () => ({
  Label: ({ children, htmlFor }: any) => (
    <label data-testid="label" htmlFor={htmlFor}>{children}</label>
  ),
}))

vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

vi.mock('../ui/loading-spinner', () => ({
  LoadingSpinner: ({ size, className }: any) => (
    <div data-testid="loading-spinner" data-size={size} className={className}>
      Loading...
    </div>
  ),
}))

vi.mock('lucide-react', () => ({
  CheckCircle: () => <div data-testid="check-circle-icon" />,
  Circle: () => <div data-testid="circle-icon" />,
  Star: () => <div data-testid="star-icon" />,
}))

describe('QuizForm', () => {
  const mockSession = {
    id: 'session-1',
    patient_id: 'patient-1',
    template_id: 'template-1',
    template_name: 'Test Quiz',
    status: 'active',
    responses: {},
    questions: [
      {
        id: 'q1',
        type: 'multiple_choice' as const,
        question: 'How are you feeling?',
        options: ['Great', 'Good', 'Okay', 'Not great'],
        required: true,
      },
      {
        id: 'q2',
        type: 'yes_no' as const,
        question: 'Are you taking medication?',
        required: false,
      },
      {
        id: 'q3',
        type: 'scale' as const,
        question: 'Rate your pain level',
        min: 1,
        max: 10,
        required: true,
      },
      {
        id: 'q4',
        type: 'text' as const,
        question: 'Any additional comments?',
        required: false,
      },
      {
        id: 'q5',
        type: 'checkbox' as const,
        question: 'Select symptoms',
        options: ['Headache', 'Nausea', 'Fatigue'],
        required: false,
      },
    ],
  }

  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    mockSubmitResponse.mockResolvedValue({ success: true })
  })

  const renderWithQueryClient = (component: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        {component}
      </QueryClientProvider>
    )
  }

  describe('Rendering', () => {
    it('should render quiz header with template name', () => {
      renderWithQueryClient(<QuizForm session={mockSession} />)

      expect(screen.getByTestId('card-title')).toHaveTextContent('Test Quiz')
      expect(screen.getByTestId('card-description')).toHaveTextContent(
        'Responda todas as perguntas para completar o questionário'
      )
    })

    it('should render all questions', () => {
      renderWithQueryClient(<QuizForm session={mockSession} />)

      expect(screen.getByText('How are you feeling?')).toBeInTheDocument()
      expect(screen.getByText('Are you taking medication?')).toBeInTheDocument()
      expect(screen.getByText('Rate your pain level')).toBeInTheDocument()
      expect(screen.getByText('Any additional comments?')).toBeInTheDocument()
      expect(screen.getByText('Select symptoms')).toBeInTheDocument()
    })

    it('should show required asterisk for required questions', () => {
      renderWithQueryClient(<QuizForm session={mockSession} />)

      const requiredQuestions = screen.getAllByText('*')
      expect(requiredQuestions).toHaveLength(2) // q1 and q3 are required
    })

    it('should show progress indicator', () => {
      renderWithQueryClient(<QuizForm session={mockSession} />)

      expect(screen.getByText('Progresso')).toBeInTheDocument()
      expect(screen.getByText('0 de 5 perguntas')).toBeInTheDocument()
    })
  })

  describe('Question Types', () => {
    describe('Multiple Choice Questions', () => {
      it('should render multiple choice options', () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        mockSession.questions[0].options?.forEach(option => {
          expect(screen.getByText(option)).toBeInTheDocument()
        })
      })

      it('should handle multiple choice selection', async () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        const radioGroup = screen.getByTestId('radio-group')
        fireEvent.click(radioGroup)

        // Progress should update
        await waitFor(() => {
          expect(screen.getByText('1 de 5 perguntas')).toBeInTheDocument()
        })
      })
    })

    describe('Yes/No Questions', () => {
      it('should render yes/no options', () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        expect(screen.getByText('Sim')).toBeInTheDocument()
        expect(screen.getByText('Não')).toBeInTheDocument()
      })
    })

    describe('Scale Questions', () => {
      it('should render scale with min/max values', () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        const slider = screen.getByTestId('slider')
        expect(slider).toHaveAttribute('min', '1')
        expect(slider).toHaveAttribute('max', '10')
      })

      it('should handle scale value changes', async () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        const slider = screen.getByTestId('slider')
        fireEvent.change(slider, { target: { value: '7' } })

        // Progress should update
        await waitFor(() => {
          expect(screen.getByText('1 de 5 perguntas')).toBeInTheDocument()
        })
      })
    })

    describe('Text Questions', () => {
      it('should render textarea for text questions', () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        const textarea = screen.getByTestId('textarea')
        expect(textarea).toHaveAttribute('placeholder', 'Digite sua resposta...')
      })

      it('should handle text input changes', async () => {
        const user = userEvent.setup()
        renderWithQueryClient(<QuizForm session={mockSession} />)

        const textarea = screen.getByTestId('textarea')
        await user.type(textarea, 'Test response')

        // Progress should update
        await waitFor(() => {
          expect(screen.getByText('1 de 5 perguntas')).toBeInTheDocument()
        })
      })
    })

    describe('Checkbox Questions', () => {
      it('should render checkbox options', () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        mockSession.questions[4].options?.forEach(option => {
          expect(screen.getByText(option)).toBeInTheDocument()
        })
      })

      it('should handle checkbox selections', async () => {
        renderWithQueryClient(<QuizForm session={mockSession} />)

        const checkboxes = screen.getAllByRole('checkbox')
        fireEvent.click(checkboxes[0])

        // Progress should update
        await waitFor(() => {
          expect(screen.getByText('1 de 5 perguntas')).toBeInTheDocument()
        })
      })
    })
  })

  describe('Form Submission', () => {
    it('should prevent submission when required questions are not answered', async () => {
      const { toast } = require('@/components/ui/use-toast').useToast()
      renderWithQueryClient(<QuizForm session={mockSession} />)

      const submitButton = screen.getByTestId('submit-button')
      fireEvent.click(submitButton)

      expect(mockSubmitResponse).not.toHaveBeenCalled()
      expect(toast).toHaveBeenCalledWith({
        title: 'Campos obrigatórios',
        description: expect.stringContaining('2 restantes'),
        variant: 'destructive'
      })
    })

    it('should submit successfully when all required questions are answered', async () => {
      const sessionWithResponses = {
        ...mockSession,
        responses: {
          q1: 'Great',
          q3: 8,
        },
      }

      const onComplete = vi.fn()
      renderWithQueryClient(
        <QuizForm session={sessionWithResponses} onComplete={onComplete} />
      )

      const submitButton = screen.getByTestId('submit-button')
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(mockSubmitResponse).toHaveBeenCalledWith('session-1', {
          q1: 'Great',
          q3: 8,
        })
      })

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalled()
      })
    })

    it('should show loading state during submission', async () => {
      mockSubmitResponse.mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 100))
      )

      const sessionWithResponses = {
        ...mockSession,
        responses: { q1: 'Great', q3: 8 },
      }

      renderWithQueryClient(<QuizForm session={sessionWithResponses} />)

      const submitButton = screen.getByTestId('submit-button')
      fireEvent.click(submitButton)

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
      expect(screen.getByText('Enviando...')).toBeInTheDocument()
      expect(submitButton).toBeDisabled()

      await waitFor(() => {
        expect(mockSubmitResponse).toHaveBeenCalled()
      })
    })

    it('should handle submission errors', async () => {
      const error = { data: { message: 'Network error' } }
      mockSubmitResponse.mockRejectedValue(error)
      const { toast } = require('@/components/ui/use-toast').useToast()

      const sessionWithResponses = {
        ...mockSession,
        responses: { q1: 'Great', q3: 8 },
      }

      renderWithQueryClient(<QuizForm session={sessionWithResponses} />)

      const submitButton = screen.getByTestId('submit-button')
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(toast).toHaveBeenCalledWith({
          title: 'Erro ao enviar questionário',
          description: 'Network error',
          variant: 'destructive'
        })
      })
    })
  })

  describe('Progress Tracking', () => {
    it('should update progress as questions are answered', async () => {
      renderWithQueryClient(<QuizForm session={mockSession} />)

      // Initially no questions answered
      expect(screen.getByText('0 de 5 perguntas')).toBeInTheDocument()

      // Answer a question
      const radioGroup = screen.getByTestId('radio-group')
      fireEvent.click(radioGroup)

      await waitFor(() => {
        expect(screen.getByText('1 de 5 perguntas')).toBeInTheDocument()
      })
    })

    it('should show completion status when all questions are answered', () => {
      const sessionWithAllResponses = {
        ...mockSession,
        responses: {
          q1: 'Great',
          q2: 'yes',
          q3: 8,
          q4: 'No comments',
          q5: ['Headache'],
        },
      }

      renderWithQueryClient(<QuizForm session={sessionWithAllResponses} />)

      expect(screen.getByText('✓ Todas as perguntas foram respondidas')).toBeInTheDocument()
    })

    it('should show remaining questions count', () => {
      const sessionWithPartialResponses = {
        ...mockSession,
        responses: {
          q1: 'Great',
          q3: 8,
        },
      }

      renderWithQueryClient(<QuizForm session={sessionWithPartialResponses} />)

      expect(screen.getByText('3 perguntas restantes')).toBeInTheDocument()
    })
  })

  describe('Visual Feedback', () => {
    it('should mark answered questions with check icon', () => {
      const sessionWithResponses = {
        ...mockSession,
        responses: { q1: 'Great' },
      }

      renderWithQueryClient(<QuizForm session={sessionWithResponses} />)

      expect(screen.getByTestId('check-circle-icon')).toBeInTheDocument()
    })

    it('should style answered question cards differently', () => {
      const sessionWithResponses = {
        ...mockSession,
        responses: { q1: 'Great' },
      }

      renderWithQueryClient(<QuizForm session={sessionWithResponses} />)

      const cards = screen.getAllByTestId('card')
      const answeredCard = cards.find(card =>
        card.className?.includes('border-green-200')
      )
      expect(answeredCard).toBeInTheDocument()
    })
  })

  describe('Existing Responses', () => {
    it('should pre-populate form with existing responses', () => {
      const sessionWithResponses = {
        ...mockSession,
        responses: {
          q1: 'Great',
          q2: 'yes',
          q3: 7,
          q4: 'Some comment',
          q5: ['Headache', 'Fatigue'],
        },
      }

      renderWithQueryClient(<QuizForm session={sessionWithResponses} />)

      // Check that progress reflects existing responses
      expect(screen.getByText('5 de 5 perguntas')).toBeInTheDocument()
    })
  })
})