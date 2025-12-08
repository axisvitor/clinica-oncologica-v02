import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { RiskBadge } from '@/features/patients/components/RiskBadge'

interface PatientRiskData {
  patient_id: string
  patient_name: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_score: number
  recent_alerts: any[]
  assessment_date: string
}

interface PhysicianRiskTableProps {
  patients: PatientRiskData[]
  totalPatients: number
  page: number
  size: number
  onPageChange: (page: number) => void
  onPatientClick: (patientId: string) => void
}

export function PhysicianRiskTable({
  patients,
  totalPatients,
  page,
  size,
  onPageChange,
  onPatientClick
}: PhysicianRiskTableProps) {
  return (
    <>
      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Paciente</TableHead>
                <TableHead>Nível de Risco</TableHead>
                <TableHead>Score de Risco</TableHead>
                <TableHead>Alertas</TableHead>
                <TableHead>Última Avaliação</TableHead>
                <TableHead>Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {patients.map((patient) => (
                <TableRow key={patient.patient_id}>
                  <TableCell className="font-medium">
                    {patient.patient_name}
                  </TableCell>
                  <TableCell>
                    <RiskBadge level={patient.risk_level} />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Progress
                        value={(patient.risk_score / 10) * 100}
                        className="w-20"
                      />
                      <span className="text-sm tabular-nums">
                        {patient.risk_score.toFixed(1)}/10
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {patient.recent_alerts.length > 0 && (
                      <Badge variant="destructive">{patient.recent_alerts.length}</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(patient.assessment_date).toLocaleDateString('pt-BR')}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onPatientClick(patient.patient_id)}
                    >
                      Detalhes
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPatients > size && (
        <div className="flex justify-between items-center">
          <p className="text-sm text-muted-foreground">
            Mostrando {Math.min((page - 1) * size + 1, totalPatients)} -{' '}
            {Math.min(page * size, totalPatients)} de {totalPatients} pacientes
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= Math.ceil(totalPatients / size)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
