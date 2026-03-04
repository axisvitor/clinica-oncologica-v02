import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Send, RefreshCw } from 'lucide-react'
import { MessageFormState } from '../types'

interface MessageFormProps {
  selectedInstance: string
  formState: MessageFormState
  onFormChange: (updates: Partial<MessageFormState>) => void
  onFileUpload: (event: React.ChangeEvent<HTMLInputElement>) => void
  onSubmit: () => void
  isPending: boolean
}

export function MessageForm({
  selectedInstance,
  formState,
  onFormChange,
  onFileUpload,
  onSubmit,
  isPending,
}: MessageFormProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Send Message</CardTitle>
        <CardDescription>Send message via {selectedInstance}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label htmlFor="recipient">Recipient Phone Number</Label>
          <Input
            id="recipient"
            placeholder="+5511999999999 or 5511999999999"
            value={formState.to}
            onChange={(e) => onFormChange({ to: e.target.value })}
          />
        </div>

        <div>
          <Label htmlFor="message">Message</Label>
          <Textarea
            id="message"
            placeholder="Type your message here..."
            value={formState.text}
            onChange={(e) => onFormChange({ text: e.target.value })}
            rows={3}
          />
        </div>

        <div>
          <Label htmlFor="media">Media File (Optional)</Label>
          <Input
            id="media"
            type="file"
            accept="image/*,audio/*,.pdf,.doc,.docx"
            onChange={onFileUpload}
          />
          {formState.mediaFile && (
            <div className="mt-2 p-2 bg-gray-50 rounded text-sm">
              Selected: {formState.mediaFile.name} (
              {(formState.mediaFile.size / 1024 / 1024).toFixed(2)}MB)
            </div>
          )}
        </div>

        {formState.mediaFile && (
          <div>
            <Label htmlFor="caption">Media Caption (Optional)</Label>
            <Input
              id="caption"
              placeholder="Caption for the media file..."
              value={formState.mediaCaption}
              onChange={(e) => onFormChange({ mediaCaption: e.target.value })}
            />
          </div>
        )}

        <Button onClick={onSubmit} disabled={isPending} className="w-full">
          {isPending ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Sending...
            </>
          ) : (
            <>
              <Send className="w-4 h-4 mr-2" />
              Send Message
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  )
}
