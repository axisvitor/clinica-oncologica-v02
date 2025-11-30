/**
 * Question Editor Component
 *
 * Reusable component for editing individual quiz questions and their options.
 */

import React, { memo } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { QuizQuestion, QuizQuestionOption } from '@/hooks/useTemplates';

interface QuestionEditorProps {
  question: QuizQuestion;
  questionNumber: number;
  onUpdate: (question: QuizQuestion) => void;
  onRemove: () => void;
}

export const QuestionEditor = memo<QuestionEditorProps>(({
  question,
  questionNumber,
  onUpdate,
  onRemove,
}) => {
  const handleFieldUpdate = (field: keyof QuizQuestion, value: unknown) => {
    onUpdate({ ...question, [field]: value });
  };

  const handleOptionUpdate = (index: number, field: keyof QuizQuestionOption, value: unknown) => {
    if (!question.options) return;
    const updatedOptions = [...question.options];
    updatedOptions[index] = { ...updatedOptions[index], [field]: value };
    onUpdate({ ...question, options: updatedOptions });
  };

  const handleAddOption = () => {
    const options = question.options || [];
    const newOption: QuizQuestionOption = {
      text: `Opção ${options.length + 1}`,
      value: `opt${options.length + 1}`,
    };
    onUpdate({ ...question, options: [...options, newOption] });
  };

  const handleRemoveOption = (index: number) => {
    if (!question.options) return;
    const updatedOptions = question.options.filter((_, i) => i !== index);
    onUpdate({ ...question, options: updatedOptions });
  };

  return (
    <Card className="p-4">
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <span className="text-sm font-medium text-muted-foreground">
            Pergunta {questionNumber}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRemove}
            className="text-red-500 hover:text-red-700"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Texto da Pergunta</Label>
            <Input
              value={question.text}
              onChange={(e) => handleFieldUpdate('text', e.target.value)}
              placeholder="Digite a pergunta"
            />
          </div>
          <div className="space-y-2">
            <Label>Tipo</Label>
            <Select
              value={question.type}
              onValueChange={(value) => handleFieldUpdate('type', value)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="multiple_choice">Múltipla Escolha</SelectItem>
                <SelectItem value="open_text">Texto Aberto</SelectItem>
                <SelectItem value="scale">Escala</SelectItem>
                <SelectItem value="yes_no">Sim/Não</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Switch
            checked={question.required ?? true}
            onCheckedChange={(checked) => handleFieldUpdate('required', checked)}
          />
          <Label>Obrigatória</Label>
        </div>

        {/* Options for multiple choice */}
        {question.type === 'multiple_choice' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Opções</Label>
              <Button type="button" variant="ghost" size="sm" onClick={handleAddOption}>
                <Plus className="h-3 w-3 mr-1" />
                Opção
              </Button>
            </div>
            {question.options?.map((option, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  value={option.text ?? ''}
                  onChange={(e) => handleOptionUpdate(index, 'text', e.target.value)}
                  placeholder={`Opção ${index + 1}`}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveOption(index)}
                  className="text-red-500"
                  disabled={(question.options?.length ?? 0) <= 2}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
});

QuestionEditor.displayName = 'QuestionEditor';
