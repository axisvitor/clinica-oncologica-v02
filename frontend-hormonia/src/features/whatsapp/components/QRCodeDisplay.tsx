import React from 'react'
import { Label } from '@/components/ui/label'

interface QRCodeDisplayProps {
  qrCode: string
}

export function QRCodeDisplay({ qrCode }: QRCodeDisplayProps) {
  return (
    <div className="mt-4">
      <Label>Scan QR Code to Connect</Label>
      <div className="mt-2 p-4 bg-white rounded border">
        <img
          src={`data:image/png;base64,${qrCode}`}
          alt="QR Code"
          width={192}
          height={192}
          className="w-48 h-48 mx-auto"
        />
      </div>
    </div>
  )
}
