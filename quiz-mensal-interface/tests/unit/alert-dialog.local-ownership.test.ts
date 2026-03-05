import fs from 'node:fs'
import path from 'node:path'

describe('alert-dialog local ownership', () => {
  it('exports quiz alert dialog symbols', async () => {
    const alertDialogModule = await import('@/components/ui/alert-dialog')

    expect(alertDialogModule.AlertDialog).toBeDefined()
    expect(alertDialogModule.AlertDialogTrigger).toBeDefined()
    expect(alertDialogModule.AlertDialogContent).toBeDefined()
    expect(alertDialogModule.AlertDialogHeader).toBeDefined()
    expect(alertDialogModule.AlertDialogFooter).toBeDefined()
    expect(alertDialogModule.AlertDialogTitle).toBeDefined()
    expect(alertDialogModule.AlertDialogDescription).toBeDefined()
    expect(alertDialogModule.AlertDialogAction).toBeDefined()
    expect(alertDialogModule.AlertDialogCancel).toBeDefined()
  })

  it('does not reference frontend-hormonia source imports', () => {
    const sourcePath = path.join(process.cwd(), 'components/ui/alert-dialog.tsx')
    const source = fs.readFileSync(sourcePath, 'utf8')

    expect(source).not.toMatch(/frontend-hormonia/)
  })
})
