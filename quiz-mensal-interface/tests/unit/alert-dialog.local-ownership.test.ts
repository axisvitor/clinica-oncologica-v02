import fs from 'node:fs'
import path from 'node:path'

describe('alert-dialog local ownership', () => {
  it('exports quiz alert dialog symbols', async () => {
    const module = await import('@/components/ui/alert-dialog')

    expect(module.AlertDialog).toBeDefined()
    expect(module.AlertDialogTrigger).toBeDefined()
    expect(module.AlertDialogContent).toBeDefined()
    expect(module.AlertDialogHeader).toBeDefined()
    expect(module.AlertDialogFooter).toBeDefined()
    expect(module.AlertDialogTitle).toBeDefined()
    expect(module.AlertDialogDescription).toBeDefined()
    expect(module.AlertDialogAction).toBeDefined()
    expect(module.AlertDialogCancel).toBeDefined()
  })

  it('does not reference frontend-hormonia source imports', () => {
    const sourcePath = path.join(process.cwd(), 'components/ui/alert-dialog.tsx')
    const source = fs.readFileSync(sourcePath, 'utf8')

    expect(source).not.toMatch(/frontend-hormonia/)
  })
})
