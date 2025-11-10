/**
 * WhatsApp Message Sender Component
 * Handles sending text, media, and template messages
 */
import React, { useState, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import {
  Send,
  Image,
  FileText,
  Paperclip,
  X,
  CheckCircle,
  AlertCircle,
  Upload,
  MessageSquare
} from 'lucide-react';
import { whatsAppService, MessageRequest, MessageResponse } from '../../services/whatsapp/WhatsAppService';

interface WhatsAppMessageSenderProps {
  instanceName: string;
  onMessageSent?: (response: MessageResponse) => void;
  onError?: (error: string) => void;
}

export const WhatsAppMessageSender: React.FC<WhatsAppMessageSenderProps> = ({
  instanceName,
  onMessageSent,
  onError
}) => {
  const [recipient, setRecipient] = useState('');
  const [messageType, setMessageType] = useState<'text' | 'image' | 'document'>('text');
  const [textMessage, setTextMessage] = useState('');
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaCaption, setMediaCaption] = useState('');
  const [sending, setSending] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isValidNumber, setIsValidNumber] = useState<boolean | null>(null);
  const [checkingNumber, setCheckingNumber] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndFormatNumber = async (phoneNumber: string) => {
    if (!phoneNumber.trim()) {
      setIsValidNumber(null);
      return;
    }

    try {
      setCheckingNumber(true);
      const validation = whatsAppService.validatePhoneNumber(phoneNumber);

      if (validation.isValid) {
        // Check if number is on WhatsApp
        const response = await whatsAppService.checkWhatsAppNumber(instanceName, validation.formatted);
        setIsValidNumber(response.isWhatsappUser);
        setRecipient(validation.formatted || '');
      } else {
        setIsValidNumber(false);
        setError(validation.error || '');
      }
    } catch (err) {
      setIsValidNumber(false);
      setError('Failed to validate phone number');
    } finally {
      setCheckingNumber(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file size (16MB max for WhatsApp)
      if (file.size > 16 * 1024 * 1024) {
        setError('File size must be less than 16MB');
        return;
      }

      // Validate file type
      const validTypes = {
        image: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
        document: ['application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
      };

      const isValidType = messageType === 'image'
        ? validTypes.image.includes(file.type)
        : validTypes.document.includes(file.type);

      if (!isValidType) {
        setError(`Invalid file type for ${messageType} message`);
        return;
      }

      setMediaFile(file);
      setError(null);
    }
  };

  const uploadMedia = async (file: File): Promise<string> => {
    try {
      setUploadProgress(0);
      const response = await whatsAppService.uploadMedia(file);
      setUploadProgress(100);
      return response.url;
    } catch (err) {
      throw new Error('Failed to upload media file');
    }
  };

  const sendMessage = async () => {
    if (!recipient.trim()) {
      setError('Recipient phone number is required');
      return;
    }

    if (messageType === 'text' && !textMessage.trim()) {
      setError('Message text is required');
      return;
    }

    if ((messageType === 'image' || messageType === 'document') && !mediaFile) {
      setError('Please select a file to send');
      return;
    }

    try {
      setSending(true);
      setError(null);
      setSuccess(null);

      const request: MessageRequest = {
        instanceName,
        to: recipient,
        messageType,
      };

      if (messageType === 'text') {
        request.text = textMessage;
      } else {
        // Upload media file first
        const mediaUrl = await uploadMedia(mediaFile!);
        request.mediaUrl = mediaUrl;
        if (mediaCaption) {
          request.mediaCaption = mediaCaption;
        }

        if (messageType === 'document') {
          request.filename = mediaFile!.name;
        }
      }

      const response = await whatsAppService.sendMessage(request);

      setSuccess(`Message sent successfully! ID: ${response.id}`);
      onMessageSent?.(response);

      // Reset form
      if (messageType === 'text') {
        setTextMessage('');
      } else {
        setMediaFile(null);
        setMediaCaption('');
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
      setUploadProgress(0);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);
      onError?.(errorMessage);
    } finally {
      setSending(false);
    }
  };

  const clearMediaFile = () => {
    setMediaFile(null);
    setMediaCaption('');
    setUploadProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5" />
          Send WhatsApp Message
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="w-4 h-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert>
            <CheckCircle className="w-4 h-4" />
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        )}

        {/* Recipient */}
        <div className="space-y-2">
          <Label htmlFor="recipient">Recipient Phone Number</Label>
          <div className="flex gap-2">
            <Input
              id="recipient"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              onBlur={() => validateAndFormatNumber(recipient)}
              placeholder="+55 11 99999-9999"
              className={`flex-1 ${
                isValidNumber === true ? 'border-green-500' :
                isValidNumber === false ? 'border-red-500' : ''
              }`}
            />
            {checkingNumber && (
              <div className="flex items-center px-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
              </div>
            )}
            {isValidNumber === true && (
              <div className="flex items-center px-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
              </div>
            )}
            {isValidNumber === false && (
              <div className="flex items-center px-2">
                <X className="w-4 h-4 text-red-500" />
              </div>
            )}
          </div>
          {isValidNumber === false && (
            <p className="text-sm text-red-600">Invalid phone number or not on WhatsApp</p>
          )}
          {isValidNumber === true && (
            <p className="text-sm text-green-600">Valid WhatsApp number</p>
          )}
        </div>

        {/* Message Type */}
        <div className="space-y-2">
          <Label htmlFor="messageType">Message Type</Label>
          <Select value={messageType} onValueChange={(value: 'text' | 'image' | 'document') => {
            setMessageType(value);
            setMediaFile(null);
            setMediaCaption('');
            setUploadProgress(0);
            if (fileInputRef.current) {
              fileInputRef.current.value = '';
            }
          }}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="text">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" />
                  Text Message
                </div>
              </SelectItem>
              <SelectItem value="image">
                <div className="flex items-center gap-2">
                  <Image className="w-4 h-4" />
                  Image
                </div>
              </SelectItem>
              <SelectItem value="document">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Document
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Text Message */}
        {messageType === 'text' && (
          <div className="space-y-2">
            <Label htmlFor="textMessage">Message Text</Label>
            <Textarea
              id="textMessage"
              value={textMessage}
              onChange={(e) => setTextMessage(e.target.value)}
              placeholder="Type your message here..."
              rows={4}
              maxLength={4096}
            />
            <p className="text-sm text-gray-500 text-right">
              {textMessage.length}/4096 characters
            </p>
          </div>
        )}

        {/* Media Message */}
        {(messageType === 'image' || messageType === 'document') && (
          <div className="space-y-4">
            {/* File Upload */}
            <div className="space-y-2">
              <Label htmlFor="mediaFile">
                {messageType === 'image' ? 'Select Image' : 'Select Document'}
              </Label>

              {!mediaFile ? (
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={messageType === 'image' ? 'image/*' : '.pdf,.doc,.docx,.txt'}
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <Button
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                    className="mb-2"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Choose File
                  </Button>
                  <p className="text-sm text-gray-500">
                    {messageType === 'image'
                      ? 'JPEG, PNG, GIF, WebP (max 16MB)'
                      : 'PDF, DOC, DOCX, TXT (max 16MB)'
                    }
                  </p>
                </div>
              ) : (
                <div className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {messageType === 'image' ? (
                        <Image className="w-5 h-5" />
                      ) : (
                        <FileText className="w-5 h-5" />
                      )}
                      <span className="font-medium">{mediaFile.name}</span>
                      <span className="text-sm text-gray-500">
                        ({(mediaFile.size / 1024 / 1024).toFixed(2)} MB)
                      </span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={clearMediaFile}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>

                  {uploadProgress > 0 && uploadProgress < 100 && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span>Uploading...</span>
                        <span>{uploadProgress}%</span>
                      </div>
                      <Progress value={uploadProgress} />
                    </div>
                  )}

                  {messageType === 'image' && (
                    <div className="mt-2">
                      <img
                        src={URL.createObjectURL(mediaFile)}
                        alt="Preview"
                        className="max-w-full h-32 object-contain rounded"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Caption */}
            <div className="space-y-2">
              <Label htmlFor="mediaCaption">Caption (Optional)</Label>
              <Textarea
                id="mediaCaption"
                value={mediaCaption}
                onChange={(e) => setMediaCaption(e.target.value)}
                placeholder="Add a caption to your file..."
                rows={2}
                maxLength={1024}
              />
              <p className="text-sm text-gray-500 text-right">
                {mediaCaption.length}/1024 characters
              </p>
            </div>
          </div>
        )}

        {/* Send Button */}
        <div className="flex justify-end pt-4">
          <Button
            onClick={sendMessage}
            disabled={
              sending ||
              !recipient.trim() ||
              isValidNumber !== true ||
              (messageType === 'text' && !textMessage.trim()) ||
              ((messageType === 'image' || messageType === 'document') && !mediaFile)
            }
            className="min-w-[120px]"
          >
            {sending ? (
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Sending...
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Send className="w-4 h-4" />
                Send Message
              </div>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default WhatsAppMessageSender;
