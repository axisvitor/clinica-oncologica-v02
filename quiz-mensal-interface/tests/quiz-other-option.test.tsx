import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { QuizInterface } from '../src/components/QuizInterface';

// Mock API calls
const mockSubmitResponse = jest.fn();
const mockApiClient = {
  post: jest.fn(),
  get: jest.fn(),
};

jest.mock('../src/lib/api-client', () => ({
  apiClient: mockApiClient,
}));

describe('Quiz Other Option Tests', () => {
  const singleChoiceQuestion = {
    id: 1,
    question_text: 'Qual é sua sintoma principal?',
    question_type: 'single_choice',
    options: [
      { id: 1, option_text: 'Dor de cabeça', option_value: 'headache' },
      { id: 2, option_text: 'Náusea', option_value: 'nausea' },
      { id: 3, option_text: 'Outra', option_value: 'other', is_other: true },
    ],
    allow_other: true,
  };

  const multipleChoiceQuestion = {
    id: 2,
    question_text: 'Quais sintomas você está sentindo? (Selecione todos)',
    question_type: 'multiple_choice',
    options: [
      { id: 4, option_text: 'Fadiga', option_value: 'fatigue' },
      { id: 5, option_text: 'Insônia', option_value: 'insomnia' },
      { id: 6, option_text: 'Outra', option_value: 'other', is_other: true },
    ],
    allow_other: true,
  };

  const questionWithoutOther = {
    id: 3,
    question_text: 'Você está tomando medicação?',
    question_type: 'single_choice',
    options: [
      { id: 7, option_text: 'Sim', option_value: 'yes' },
      { id: 8, option_text: 'Não', option_value: 'no' },
    ],
    allow_other: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockApiClient.post.mockResolvedValue({ data: { success: true } });
  });

  describe('Single Choice - Other Option', () => {
    test('should render "Outra" option for single choice question', () => {
      render(<QuizInterface question={singleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      expect(otherOption).toBeInTheDocument();
      expect(otherOption).toHaveAttribute('type', 'radio');
    });

    test('should show text input when "Outra" is selected', async () => {
      render(<QuizInterface question={singleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      await waitFor(() => {
        const textInput = screen.getByPlaceholderText(/Especifique outra opção/i);
        expect(textInput).toBeInTheDocument();
        expect(textInput).toBeVisible();
      });
    });

    test('should hide text input when another option is selected', async () => {
      render(<QuizInterface question={singleChoiceQuestion} />);

      // Select "Outra"
      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Especifique outra opção/i)).toBeVisible();
      });

      // Select another option
      const headacheOption = screen.getByLabelText(/Dor de cabeça/i);
      fireEvent.click(headacheOption);

      await waitFor(() => {
        const textInput = screen.queryByPlaceholderText(/Especifique outra opção/i);
        expect(textInput).not.toBeInTheDocument();
      });
    });

    test('should allow typing custom text in other input', async () => {
      const user = userEvent.setup();
      render(<QuizInterface question={singleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, 'Tontura persistente');

      expect(textInput).toHaveValue('Tontura persistente');
    });

    test('should show validation error when submitting "Outra" without text', async () => {
      render(<QuizInterface question={singleChoiceQuestion} onSubmit={mockSubmitResponse} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Por favor, especifique a opção/i)).toBeInTheDocument();
      });

      expect(mockSubmitResponse).not.toHaveBeenCalled();
    });

    test('should submit successfully with custom text', async () => {
      const user = userEvent.setup();
      const onSubmit = jest.fn();

      render(<QuizInterface question={singleChoiceQuestion} onSubmit={onSubmit} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, 'Tontura persistente');

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          question_id: 1,
          selected_options: [3],
          other_text: 'Tontura persistente',
        });
      });
    });
  });

  describe('Multiple Choice - Other Option', () => {
    test('should allow selecting "Outra" along with other options', async () => {
      const user = userEvent.setup();
      render(<QuizInterface question={multipleChoiceQuestion} />);

      // Select multiple options including "Outra"
      const fatigueOption = screen.getByLabelText(/Fadiga/i);
      const otherOption = screen.getByLabelText(/Outra/i);

      fireEvent.click(fatigueOption);
      fireEvent.click(otherOption);

      expect(fatigueOption).toBeChecked();
      expect(otherOption).toBeChecked();

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      expect(textInput).toBeVisible();
    });

    test('should preserve other selections when typing custom text', async () => {
      const user = userEvent.setup();
      render(<QuizInterface question={multipleChoiceQuestion} />);

      const fatigueOption = screen.getByLabelText(/Fadiga/i);
      const insomniaOption = screen.getByLabelText(/Insônia/i);
      const otherOption = screen.getByLabelText(/Outra/i);

      fireEvent.click(fatigueOption);
      fireEvent.click(insomniaOption);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, 'Dor muscular');

      expect(fatigueOption).toBeChecked();
      expect(insomniaOption).toBeChecked();
      expect(otherOption).toBeChecked();
      expect(textInput).toHaveValue('Dor muscular');
    });

    test('should submit multiple selections with custom text', async () => {
      const user = userEvent.setup();
      const onSubmit = jest.fn();

      render(<QuizInterface question={multipleChoiceQuestion} onSubmit={onSubmit} />);

      const fatigueOption = screen.getByLabelText(/Fadiga/i);
      const otherOption = screen.getByLabelText(/Outra/i);

      fireEvent.click(fatigueOption);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, 'Ansiedade');

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          question_id: 2,
          selected_options: [4, 6],
          other_text: 'Ansiedade',
        });
      });
    });

    test('should validate that at least one option is selected', async () => {
      render(<QuizInterface question={multipleChoiceQuestion} onSubmit={mockSubmitResponse} />);

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Por favor, selecione pelo menos uma opção/i)).toBeInTheDocument();
      });

      expect(mockSubmitResponse).not.toHaveBeenCalled();
    });
  });

  describe('Persistence and Navigation', () => {
    test('should persist custom text when navigating between questions', async () => {
      const user = userEvent.setup();
      const { rerender } = render(<QuizInterface question={singleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, 'Minha resposta customizada');

      // Navigate to another question
      rerender(<QuizInterface question={questionWithoutOther} />);

      // Navigate back
      rerender(<QuizInterface question={singleChoiceQuestion} />);

      const otherOptionAgain = screen.getByLabelText(/Outra/i);
      expect(otherOptionAgain).toBeChecked();

      const textInputAgain = await screen.findByPlaceholderText(/Especifique outra opção/i);
      expect(textInputAgain).toHaveValue('Minha resposta customizada');
    });

    test('should clear custom text when deselecting "Outra"', async () => {
      const user = userEvent.setup();
      render(<QuizInterface question={multipleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, 'Texto temporário');

      // Deselect "Outra"
      fireEvent.click(otherOption);

      await waitFor(() => {
        expect(screen.queryByPlaceholderText(/Especifique outra opção/i)).not.toBeInTheDocument();
      });

      // Select "Outra" again
      fireEvent.click(otherOption);

      const newTextInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      expect(newTextInput).toHaveValue('');
    });
  });

  describe('Questions without Other Option', () => {
    test('should not show "Outra" when allow_other is false', () => {
      render(<QuizInterface question={questionWithoutOther} />);

      const otherOption = screen.queryByLabelText(/Outra/i);
      expect(otherOption).not.toBeInTheDocument();
    });

    test('should submit normally without other_text field', async () => {
      const onSubmit = jest.fn();
      render(<QuizInterface question={questionWithoutOther} onSubmit={onSubmit} />);

      const yesOption = screen.getByLabelText(/Sim/i);
      fireEvent.click(yesOption);

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          question_id: 3,
          selected_options: [7],
          other_text: undefined,
        });
      });
    });
  });

  describe('Edge Cases', () => {
    test('should trim whitespace from custom text', async () => {
      const user = userEvent.setup();
      const onSubmit = jest.fn();

      render(<QuizInterface question={singleChoiceQuestion} onSubmit={onSubmit} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, '   Texto com espaços   ');

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          question_id: 1,
          selected_options: [3],
          other_text: 'Texto com espaços',
        });
      });
    });

    test('should reject only whitespace as custom text', async () => {
      const user = userEvent.setup();
      render(<QuizInterface question={singleChoiceQuestion} onSubmit={mockSubmitResponse} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, '     ');

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Por favor, especifique a opção/i)).toBeInTheDocument();
      });

      expect(mockSubmitResponse).not.toHaveBeenCalled();
    });

    test('should enforce max length for custom text', async () => {
      const user = userEvent.setup();
      render(<QuizInterface question={singleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      const longText = 'a'.repeat(300);
      await user.type(textInput, longText);

      expect(textInput).toHaveValue(longText.substring(0, 255)); // Assuming 255 char limit
    });

    test('should handle special characters in custom text', async () => {
      const user = userEvent.setup();
      const onSubmit = jest.fn();

      render(<QuizInterface question={singleChoiceQuestion} onSubmit={onSubmit} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);
      await user.type(textInput, 'Dor < 5/10, com "pontadas"');

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          question_id: 1,
          selected_options: [3],
          other_text: 'Dor < 5/10, com "pontadas"',
        });
      });
    });
  });

  describe('Accessibility', () => {
    test('should associate text input with "Outra" option for screen readers', async () => {
      render(<QuizInterface question={singleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const textInput = await screen.findByPlaceholderText(/Especifique outra opção/i);

      expect(textInput).toHaveAttribute('aria-label');
      expect(textInput).toHaveAttribute('id');
    });

    test('should announce validation errors to screen readers', async () => {
      render(<QuizInterface question={singleChoiceQuestion} onSubmit={mockSubmitResponse} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      fireEvent.click(otherOption);

      const submitButton = screen.getByRole('button', { name: /Próxima|Enviar/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        const errorMessage = screen.getByText(/Por favor, especifique a opção/i);
        expect(errorMessage).toHaveAttribute('role', 'alert');
        expect(errorMessage).toHaveAttribute('aria-live', 'polite');
      });
    });

    test('should have proper focus management', async () => {
      const user = userEvent.setup();
      render(<QuizInterface question={singleChoiceQuestion} />);

      const otherOption = screen.getByLabelText(/Outra/i);
      await user.click(otherOption);

      await waitFor(() => {
        const textInput = screen.getByPlaceholderText(/Especifique outra opção/i);
        expect(textInput).toHaveFocus();
      });
    });
  });
});