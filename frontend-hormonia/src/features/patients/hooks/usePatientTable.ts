/**
 * usePatientTable Hook
 * Manages patient table state (quiz modal, selected patient)
 */

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

interface SelectedPatient {
  id: string
  name: string
}

export function usePatientTable() {
  const queryClient = useQueryClient()
  const [selectedPatient, setSelectedPatient] = useState<SelectedPatient | null>(null)
  const [showSendQuizModal, setShowSendQuizModal] = useState(false)

  const handleSendQuiz = (patient: SelectedPatient) => {
    setSelectedPatient(patient)
    setShowSendQuizModal(true)
  }

  const handleQuizSuccess = () => {
    setSelectedPatient(null)
    queryClient.invalidateQueries({ queryKey: ['monthly-quiz-status'] })
  }

  const handleCloseQuizModal = () => {
    setShowSendQuizModal(false)
  }

  return {
    selectedPatient,
    showSendQuizModal,
    handleSendQuiz,
    handleQuizSuccess,
    handleCloseQuizModal,
    setShowSendQuizModal,
  }
}
