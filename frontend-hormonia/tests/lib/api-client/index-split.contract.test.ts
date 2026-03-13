import { readFileSync } from 'node:fs'
import path from 'node:path'

import { ApiClient, ApiError, apiClient } from '@/lib/api-client'
import { describe, expect, it } from 'vitest'

const readRepoFile = (relativePath: string) =>
  readFileSync(path.resolve(process.cwd(), relativePath), 'utf8')

const escapeForRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const expectedNamespaces = [
  'auth',
  'patients',
  'appointments',
  'treatments',
  'medications',
  'monthlyQuiz',
  'analytics',
  'adminV2',
  'dashboard',
  'tasks',
  'messages',
  'flows',
  'alerts',
  'reports',
  'admin',
  'adminUsers',
  'ai',
  'quiz',
  'quizzes',
  'notifications',
  'physician',
  'hiveMind',
] as const

const remainingInlineNamespaces = [
  { property: 'messages', modulePath: './messages', inlineFactory: 'createMessagesApi' },
  { property: 'flows', modulePath: './flows', inlineFactory: 'createFlowsApi' },
  { property: 'alerts', modulePath: './alerts', inlineFactory: 'createAlertsApi' },
  { property: 'reports', modulePath: './reports', inlineFactory: 'createReportsApi' },
  { property: 'admin', modulePath: './admin-legacy', inlineFactory: 'createAdminApi' },
  { property: 'adminUsers', modulePath: './admin-users', inlineFactory: 'createAdminUsersApi' },
  { property: 'ai', modulePath: './ai', inlineFactory: 'createAiApi' },
  { property: 'quiz', modulePath: './quiz', inlineFactory: 'createQuizApi' },
  { property: 'quizzes', modulePath: './quizzes', inlineFactory: 'createQuizTemplatesApi' },
  { property: 'notifications', modulePath: './notifications', inlineFactory: 'createNotificationsApi' },
  { property: 'physician', modulePath: './physician', inlineFactory: 'createPhysicianApi' },
] as const

describe('api-client index split contract', () => {
  it('keeps the stable apiClient facade surface available at @/lib/api-client', () => {
    expect(apiClient).toBeInstanceOf(ApiClient)
    expect(ApiError).toBeTypeOf('function')

    for (const namespace of expectedNamespaces) {
      expect(apiClient).toHaveProperty(namespace)
      expect(apiClient[namespace]).toBeDefined()
    }
  })

  it('imports each remaining namespace from a dedicated createXApi(client) module', () => {
    const indexSource = readRepoFile('src/lib/api-client/index.ts')

    const missingModuleImports = remainingInlineNamespaces
      .filter(({ modulePath }) => !new RegExp(`from ['\"]${escapeForRegex(modulePath)}['\"]`).test(indexSource))
      .map(({ property, modulePath }) => `${property} -> ${modulePath}`)

    expect(
      missingModuleImports,
      `Expected src/lib/api-client/index.ts to delegate the remaining inline namespaces through dedicated modules. Missing imports: ${missingModuleImports.join(', ') || 'none'}`,
    ).toEqual([])
  })

  it('stops defining the remaining namespace factories inline inside src/lib/api-client/index.ts', () => {
    const indexSource = readRepoFile('src/lib/api-client/index.ts')

    const inlineFactoriesStillPresent = remainingInlineNamespaces
      .filter(({ inlineFactory }) =>
        new RegExp(`private\\s+${escapeForRegex(inlineFactory)}\\s*\\(`).test(indexSource),
      )
      .map(({ property, inlineFactory }) => `${property} -> ${inlineFactory}`)

    expect(
      inlineFactoriesStillPresent,
      `Expected src/lib/api-client/index.ts to stop owning inline namespace factories once the split lands. Still inline: ${inlineFactoriesStillPresent.join(', ') || 'none'}`,
    ).toEqual([])
  })

  it('wires each remaining namespace via delegated createXApi(this) composition', () => {
    const indexSource = readRepoFile('src/lib/api-client/index.ts')

    const nonDelegatedAssignments = remainingInlineNamespaces
      .filter(({ property }) => !new RegExp(`this\\.${escapeForRegex(property)}\\s*=\\s*create[A-Z][A-Za-z0-9]*Api\\(this\\)`).test(indexSource))
      .map(({ property }) => property)

    expect(
      nonDelegatedAssignments,
      `Expected the ApiClient constructor to compose delegated namespaces with createXApi(this). Non-delegated assignments: ${nonDelegatedAssignments.join(', ') || 'none'}`,
    ).toEqual([])
  })
})
