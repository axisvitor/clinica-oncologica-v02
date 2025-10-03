/**
 * Quiz Link Generator Component
 *
 * Component for creating monthly quiz links in the admin interface.
 */
import React, { useState } from 'react';
import { useMonthlyQuiz } from '../hooks/useMonthlyQuiz';
import { DeliveryMethod, MonthlyQuizLinkCreate } from '../types';

interface QuizLinkGeneratorProps {
  patientId: string;
  quizTemplateId: string;
  onLinkCreated?: (link: any) => void;
}

export const QuizLinkGenerator: React.FC<QuizLinkGeneratorProps> = ({
  patientId,
  quizTemplateId,
  onLinkCreated
}) => {
  const { createQuizLink, loading, error } = useMonthlyQuiz();
  const [deliveryMethod, setDeliveryMethod] = useState<DeliveryMethod>(DeliveryMethod.WHATSAPP);
  const [expiryHours, setExpiryHours] = useState<number>(72);
  const [customMessage, setCustomMessage] = useState<string>('');
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);

  const handleGenerateLink = async () => {
    const linkData: MonthlyQuizLinkCreate = {
      patient_id: patientId,
      quiz_template_id: quizTemplateId,
      delivery_method: deliveryMethod,
      expiry_hours: expiryHours,
      ...(customMessage && { custom_message: customMessage })
    };

    const link = await createQuizLink(linkData);

    if (link) {
      setGeneratedLink(link.link_url);
      onLinkCreated?.(link);
    }
  };

  const copyToClipboard = () => {
    if (generatedLink) {
      navigator.clipboard.writeText(generatedLink);
      alert('Link copiado para área de transferência!');
    }
  };

  return (
    <div className="quiz-link-generator p-4 border rounded-lg">
      <h3 className="text-lg font-semibold mb-4">Gerar Link de Quiz Mensal</h3>

      <div className="space-y-4">
        {/* Delivery Method */}
        <div>
          <label className="block text-sm font-medium mb-2">Método de Entrega</label>
          <select
            value={deliveryMethod}
            onChange={(e) => setDeliveryMethod(e.target.value as DeliveryMethod)}
            className="w-full p-2 border rounded"
          >
            <option value={DeliveryMethod.WHATSAPP}>WhatsApp</option>
            <option value={DeliveryMethod.EMAIL}>Email</option>
            <option value={DeliveryMethod.SMS}>SMS</option>
            <option value={DeliveryMethod.MANUAL}>Manual</option>
          </select>
        </div>

        {/* Expiry Hours */}
        <div>
          <label className="block text-sm font-medium mb-2">Validade (horas)</label>
          <input
            type="number"
            value={expiryHours}
            onChange={(e) => setExpiryHours(parseInt(e.target.value))}
            className="w-full p-2 border rounded"
            min="1"
            max="720"
          />
        </div>

        {/* Custom Message */}
        <div>
          <label className="block text-sm font-medium mb-2">Mensagem Personalizada (Opcional)</label>
          <textarea
            value={customMessage}
            onChange={(e) => setCustomMessage(e.target.value)}
            className="w-full p-2 border rounded"
            rows={3}
            placeholder="Digite uma mensagem personalizada para o paciente..."
          />
        </div>

        {/* Error Display */}
        {error && (
          <div className="p-3 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Generated Link Display */}
        {generatedLink && (
          <div className="p-3 bg-green-100 rounded">
            <p className="text-sm font-medium mb-2">Link Gerado:</p>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={generatedLink}
                readOnly
                className="flex-1 p-2 border rounded bg-white"
              />
              <button
                onClick={copyToClipboard}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                Copiar
              </button>
            </div>
          </div>
        )}

        {/* Generate Button */}
        <button
          onClick={handleGenerateLink}
          disabled={loading}
          className="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
        >
          {loading ? 'Gerando...' : 'Gerar Link'}
        </button>
      </div>
    </div>
  );
};