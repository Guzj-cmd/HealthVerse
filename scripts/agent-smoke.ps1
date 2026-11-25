param(
    [string]$BaseUrl = "http://localhost:8080/HealthVerse_Submission"
)

$payloadPath = Join-Path $PSScriptRoot "..\samples\agent-request.example.json"
$payload = Get-Content -Raw -LiteralPath $payloadPath

Write-Host "Checking health endpoint..."
Invoke-RestMethod -Uri "$BaseUrl/api/health" -Method Get

Write-Host "Checking Agent endpoint..."
Invoke-RestMethod -Uri "$BaseUrl/api/agent" -Method Post -ContentType "application/json; charset=utf-8" -Body $payload
