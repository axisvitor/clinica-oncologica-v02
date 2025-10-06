# Apply ENV fixes script
Write-Host "Applying ENV corrections..." -ForegroundColor Cyan

# Backend
if (Test-Path "backend-hormonia\.env.FINAL") {
    if (Test-Path "backend-hormonia\.env") {
        Copy-Item "backend-hormonia\.env" "backend-hormonia\.env.backup" -Force
        Write-Host "Backend .env backed up" -ForegroundColor Green
    }
    Copy-Item "backend-hormonia\.env.FINAL" "backend-hormonia\.env" -Force
    Write-Host "Backend .env updated" -ForegroundColor Green
}

# Frontend
if (Test-Path "frontend-hormonia\.env.FINAL") {
    if (Test-Path "frontend-hormonia\.env") {
        Copy-Item "frontend-hormonia\.env" "frontend-hormonia\.env.backup" -Force
        Write-Host "Frontend .env backed up" -ForegroundColor Green
    }
    Copy-Item "frontend-hormonia\.env.FINAL" "frontend-hormonia\.env" -Force
    Write-Host "Frontend .env updated" -ForegroundColor Green
}

Write-Host "`nAll ENV files updated successfully!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Deploy will trigger automatically on git push" -ForegroundColor White
Write-Host "2. Update Railway variables (see documentation)" -ForegroundColor White
