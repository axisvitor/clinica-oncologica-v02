import { readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

const readRepoFile = (relativePath: string) =>
  readFileSync(path.resolve(process.cwd(), relativePath), 'utf8')

const canonicalPatientTypeSources = [
  '@/types/api',
  '../types/api',
  '@/lib/api-client/patients',
  '../lib/api-client/patients',
] as const

describe('usePatients canonical import contract', () => {
  it('does not keep the hook on the src/lib/types/api compatibility barrel', () => {
    const usePatientsSource = readRepoFile('src/hooks/usePatients.ts')

    expect(
      usePatientsSource,
      'Expected src/hooks/usePatients.ts to stop importing Patient from src/lib/types/api once the canonical type path is in place.',
    ).not.toMatch(/from ['\"]\.\.\/lib\/types\/api['\"]/)
  })

  it('imports Patient from an allowed canonical source instead of the compat barrel', () => {
    const usePatientsSource = readRepoFile('src/hooks/usePatients.ts')
    const patientImportSources = Array.from(
      usePatientsSource.matchAll(
        /import\s+type\s+\{[^}]*\bPatient\b[^}]*\}\s+from\s+['\"]([^'\"]+)['\"]/g,
      ),
    ).map((match) => match[1])

    expect(
      patientImportSources,
      'Expected src/hooks/usePatients.ts to import Patient from a canonical source once the compat barrel is isolated.',
    ).toHaveLength(1)

    expect(
      patientImportSources[0],
      `Expected Patient in src/hooks/usePatients.ts to come from one of: ${canonicalPatientTypeSources.join(', ')}`,
    ).toBeDefined()
    expect(canonicalPatientTypeSources).toContain(
      patientImportSources[0] as (typeof canonicalPatientTypeSources)[number],
    )
  })
})
