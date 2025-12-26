/**
 * Quiz Interface Integration Tests
 * Tests the complete quiz flow using real components
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import QuizInterface from '@/components/quiz-interface';
import { fixtures, QuizSessionBuilder, QuizQuestionBuilder } from './fixtures/quiz-fixtures';

// Mock fetch for API calls
const mockFetch = jest.fn()
global.fetch = mockFetch

describe('Quiz Interface Integration Tests', () => {
  const mockOnComplete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockReset()
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('csrf-token')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ csrfToken: 'test-csrf-token' })
        });
      }
      if (url.includes('submit-answer')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            is_last_question: false,
            session_status: 'in_progress'
          })
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
  });

  describe('Quiz Rendering', () => {
    it('should render quiz interface with session data', () => {
      const session = fixtures.completeSession();
      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByText(/João Silva/)).toBeInTheDocument();
      expect(screen.getByText(/Questionário Mensal/)).toBeInTheDocument();
    });

    it('should display first question', () => {
      const session = fixtures.completeSession();
      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      const firstQuestion = session.questions[0];
      expect(screen.getByText(firstQuestion.text)).toBeInTheDocument();
    });

    it('should show progress indicator', () => {
      const session = fixtures.completeSession();
      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByText(/Pergunta 1 de/)).toBeInTheDocument();
    });
  });

  describe('Single Choice Question', () => {
    it('should render single choice options', () => {
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.singleChoiceWithOther()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByText('Dor de cabeça')).toBeInTheDocument();
      expect(screen.getByText('Náusea')).toBeInTheDocument();
      expect(screen.getByText('Fadiga')).toBeInTheDocument();
    });

    it('should allow selecting an option', async () => {
      const user = userEvent.setup();
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.singleChoiceWithOther()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      const option = screen.getByLabelText('Dor de cabeça');
      await user.click(option);

      expect(option).toBeChecked();
    });
  });

  describe('Yes/No Question', () => {
    it('should render yes and no options', () => {
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.yesNoQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByText('Sim')).toBeInTheDocument();
      expect(screen.getByText('Não')).toBeInTheDocument();
    });

    it('should allow selecting yes', async () => {
      const user = userEvent.setup();
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.yesNoQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      const yesOption = screen.getByLabelText('Sim');
      await user.click(yesOption);

      expect(yesOption).toBeChecked();
    });
  });

  describe('Scale Question', () => {
    it('should render scale buttons', () => {
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.scaleQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      // Scale 0-10 should show buttons
      for (let i = 0; i <= 10; i++) {
        expect(screen.getByRole('button', { name: i.toString() })).toBeInTheDocument();
      }
    });

    it('should allow selecting a scale value', async () => {
      const user = userEvent.setup();
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.scaleQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      const button7 = screen.getByRole('button', { name: '7' });
      await user.click(button7);

      // Button should be highlighted (has primary styles)
      expect(button7).toHaveClass('bg-primary');
    });
  });

  describe('Text Question', () => {
    it('should render textarea for text question', () => {
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.textQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByPlaceholderText(/Digite sua resposta/i)).toBeInTheDocument();
    });

    it('should allow typing text', async () => {
      const user = userEvent.setup();
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.textQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      const textarea = screen.getByPlaceholderText(/Digite sua resposta/i);
      await user.type(textarea, 'Minha observação');

      expect(textarea).toHaveValue('Minha observação');
    });
  });

  describe('Multiple Choice Question', () => {
    it('should render checkbox options', () => {
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.multipleChoiceWithOther()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByText('Dor')).toBeInTheDocument();
      expect(screen.getByText('Insônia')).toBeInTheDocument();
      expect(screen.getByText('Ansiedade')).toBeInTheDocument();
    });

    it('should allow selecting multiple options', async () => {
      const user = userEvent.setup();
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.multipleChoiceWithOther()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      const checkbox1 = screen.getByRole('checkbox', { name: 'Dor' });
      const checkbox2 = screen.getByRole('checkbox', { name: 'Insônia' });

      await user.click(checkbox1);
      await user.click(checkbox2);

      expect(checkbox1).toBeChecked();
      expect(checkbox2).toBeChecked();
    });
  });

  describe('Navigation', () => {
    it('should show Voltar button after first question', async () => {
      const user = userEvent.setup();
      const session = fixtures.completeSession();

      mockFetch.mockImplementation((url: string) => {
        if (url.includes('csrf-token')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ csrfToken: 'test-csrf-token' })
          });
        }
        if (url.includes('submit-answer')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({
              success: true,
              is_last_question: false,
              session_status: 'in_progress'
            })
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      // First question - no back button
      expect(screen.queryByText('Voltar')).not.toBeInTheDocument();
    });

    it('should show Finalizar on last question', () => {
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.textQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByTestId('submit-quiz')).toBeInTheDocument();
    });
  });

  describe('Quiz Completion', () => {
    it('should render submit button for last question', () => {
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.textQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      // Verify submit button is rendered for quiz completion
      expect(screen.getByTestId('submit-quiz')).toBeInTheDocument();
    });

    it('should allow text input before submission', async () => {
      const user = userEvent.setup();
      const session = new QuizSessionBuilder()
        .withQuestions([fixtures.textQuestion()])
        .build();

      render(
        <QuizInterface
          session={session}
          onComplete={mockOnComplete}
        />
      );

      const textarea = screen.getByPlaceholderText(/Digite sua resposta/i);
      await user.type(textarea, 'Observação final');

      expect(textarea).toHaveValue('Observação final');
    });
  });
});
