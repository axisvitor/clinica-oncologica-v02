import fs from 'node:fs'
import path from 'node:path'

describe('toast local ownership', () => {
  it('references quiz-local toast shared primitives', () => {
    const sourcePath = path.join(process.cwd(), 'components/ui/toast.tsx')
    const source = fs.readFileSync(sourcePath, 'utf8')

    expect(source).toMatch(/from ['\"]\.\/toast-shared-primitives['\"]/)
    expect(source).not.toMatch(/frontend-hormonia/)
  })

  it('has local toast shared primitives file', () => {
    const primitivesPath = path.join(process.cwd(), 'components/ui/toast-shared-primitives.tsx')
    expect(fs.existsSync(primitivesPath)).toBe(true)
  })
})
