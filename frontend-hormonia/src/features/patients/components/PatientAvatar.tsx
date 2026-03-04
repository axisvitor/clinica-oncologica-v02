/**
 * PatientAvatar Component
 * Displays patient avatar with initials fallback
 */

import React from 'react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { getInitials } from '../utils'

interface PatientAvatarProps {
  name: string
  imageUrl?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZE_CLASSES = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-12 w-12 text-base',
}

export const PatientAvatar: React.FC<PatientAvatarProps> = ({
  name,
  imageUrl = '',
  size = 'sm',
  className = '',
}) => {
  const sizeClass = SIZE_CLASSES[size]

  return (
    <Avatar className={`${sizeClass} flex-shrink-0 ${className}`}>
      <AvatarImage src={imageUrl} alt={name} />
      <AvatarFallback className="bg-blue-600 text-white">{getInitials(name)}</AvatarFallback>
    </Avatar>
  )
}
