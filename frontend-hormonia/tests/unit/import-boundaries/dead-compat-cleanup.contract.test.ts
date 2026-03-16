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

const deletedBridgeAndResidueFiles = [
  'lib/flow-engine/FlowEngine.ts',
  'lib/flow-engine/TemplateManager.ts',
  'lib/types/ai.ts',
  'lib/types/api.ts',
  'lib/types/flow.ts',
  'lib/types/flow-designer.ts',
  'lib/types/messages.ts',
  'lib/types/message-types.ts',
  'firebase.json',
  '.firebaserc',
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

  it('keeps dead bridge files and Firebase Hosting residue deleted after S03-M006', () => {
    const resurrectedFiles = deletedBridgeAndResidueFiles.filter((relativePath) =>
      existsSync(resolveRepoPath(relativePath)),
    )

    expect(
      resurrectedFiles,
      `Expected S03-M006 cleanup to keep these bridge/residue files deleted: ${deletedBridgeAndResidueFiles.join(', ')}`,
    ).toEqual([])
  })

  it('keeps root lib/flow-engine/ and lib/types/ directories removed', () => {
    const zombieDirs = ['lib/flow-engine', 'lib/types'].filter((dir) =>
      existsSync(resolveRepoPath(dir)),
    )

    expect(
      zombieDirs,
      'Expected empty bridge/barrel directories to stay removed after S03-M006 cleanup.',
    ).toEqual([])
  })
})
