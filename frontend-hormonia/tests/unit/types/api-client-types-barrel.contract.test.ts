import { readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

const readRepoFile = (relativePath: string) =>
  readFileSync(path.resolve(process.cwd(), relativePath), 'utf8')

describe('api-client types barrel contract', () => {
  it('keeps RiskAssessmentRequest visible from the stable transport barrel', () => {
    const typesSource = readRepoFile('src/lib/api-client/types.ts')

    expect(typesSource).toContain('RiskAssessmentRequest')
  })

  it('re-exports quiz and physician transport types from dedicated barrel modules', () => {
    const typesSource = readRepoFile('src/lib/api-client/types.ts')

    const missingBarrelExports = ['./types/quiz', './types/physician'].filter(
      (modulePath) => !new RegExp(`from ['\"]${modulePath.replace('/', '\\/')}['\"]`).test(typesSource),
    )

    expect(
      missingBarrelExports,
      `Expected src/lib/api-client/types.ts to behave as a barrel over dedicated domain type modules. Missing re-export wiring: ${missingBarrelExports.join(', ') || 'none'}`,
    ).toEqual([])
  })

  it('keeps RiskAssessmentRequest owned in exactly one canonical domain module', () => {
    const typesSource = readRepoFile('src/lib/api-client/types.ts')
    const quizSource = readRepoFile('src/lib/api-client/types/quiz.ts')
    const physicianSource = readRepoFile('src/lib/api-client/types/physician.ts')

    const barrelDeclarations =
      typesSource.match(/export\s+(?:interface|type)\s+RiskAssessmentRequest\b/g) ?? []
    const quizDeclarations =
      quizSource.match(/export\s+(?:interface|type)\s+RiskAssessmentRequest\b/g) ?? []
    const physicianDeclarations =
      physicianSource.match(/export\s+(?:interface|type)\s+RiskAssessmentRequest\b/g) ?? []

    expect(
      barrelDeclarations,
      'Expected src/lib/api-client/types.ts to re-export RiskAssessmentRequest instead of declaring it inline.',
    ).toHaveLength(0)
    expect(
      quizDeclarations,
      'Expected src/lib/api-client/types/quiz.ts to stop owning RiskAssessmentRequest once physician becomes the canonical transport owner.',
    ).toHaveLength(0)
    expect(
      physicianDeclarations,
      `Expected src/lib/api-client/types/physician.ts to own exactly one RiskAssessmentRequest declaration, but found ${physicianDeclarations.length}.`,
    ).toHaveLength(1)
  })
})
