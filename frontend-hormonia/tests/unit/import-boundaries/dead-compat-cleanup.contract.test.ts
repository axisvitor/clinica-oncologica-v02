import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

const resolveRepoPath = (relativePath: string) => path.resolve(process.cwd(), relativePath)
const readRepoFile = (relativePath: string) => readFileSync(resolveRepoPath(relativePath), 'utf8')

const deletedCompatFiles = [
  'src/lib/api.ts',
  'src/lib/types/api.ts',
  'src/hooks/use-quiz-session.ts',
] as const

describe('dead compat cleanup contract', () => {
  it('keeps the proven-dead frontend compatibility files deleted after S04', () => {
    const resurrectedCompatFiles = deletedCompatFiles.filter((relativePath) =>
      existsSync(resolveRepoPath(relativePath)),
    )

    expect(
      resurrectedCompatFiles,
      `Expected S04 cleanup to keep these compatibility files deleted: ${deletedCompatFiles.join(', ')}`,
    ).toEqual([])
  })

  it('keeps the focused type validation proof off the legacy compat barrel', () => {
    const typeValidationSource = readRepoFile('tests/unit/types-validation.test.ts')

    expect(
      typeValidationSource,
      'Expected tests/unit/types-validation.test.ts to stop importing from src/lib/types/api after the S04 compat cleanup.',
    ).not.toMatch(/from ['\"][^'\"]*lib\/types\/api['\"]/)
  })
})
