#requires -Version 5.1
<#
Gate de integridade e antivírus do pacote Windows DUELTRACE WebUI.
Falha fechada: se Defender estiver indisponível/desativado, não aprova release.
Não assina código e não substitui avaliação independente de malware.
#>
param(
    [Parameter(Mandatory=$true)][string]$PackageDirectory,
    [Parameter(Mandatory=$true)][string]$ZipPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference="Stop"
$package=(Resolve-Path $PackageDirectory).Path
$archive=(Resolve-Path $ZipPath).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$report=(Resolve-Path $OutputDirectory).Path
$exe=Join-Path $package "DUELTRACE-WebUI.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Executável ausente." }
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { throw "ZIP ausente." }

# Bloqueia uploads não determinísticos ou com arquivos de análise na distribuição.
$forbidden=Get-ChildItem -LiteralPath $package -Recurse -Force -File |
    Where-Object { $_.Name -match '(?i)^(?:\.env(?:\..*)?|id_rsa|.*\.p12|.*\.pfx|.*\.pem|.*\.key)$' }
if ($forbidden) { throw "Segredo/certificado não pode entrar no pacote Windows." }

if (-not (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue)) {
    throw "Microsoft Defender não disponível no runner. Pacote NÃO aprovado."
}
$status=Get-MpComputerStatus -ErrorAction Stop
if ($status.AntivirusEnabled -ne $true -or $status.AMServiceEnabled -ne $true) {
    throw "Microsoft Defender não está ativo. Pacote NÃO aprovado."
}
if ($null -eq $status.AntivirusSignatureAge -or $status.AntivirusSignatureAge -gt 7) {
    throw "Assinatura antivírus ausente/desatualizada. Pacote NÃO aprovado."
}
$scanStarted=Get-Date
Start-MpScan -ScanPath $package -ScanType CustomScan -ErrorAction Stop
Start-MpScan -ScanPath $archive -ScanType CustomScan -ErrorAction Stop

$detections=@(Get-MpThreatDetection -ErrorAction Stop |
    Where-Object { $_.InitialDetectionTime -ge $scanStarted })
if ($detections.Count -ne 0) {
    throw "Microsoft Defender identificou ameaça durante o exame. Pacote NÃO aprovado."
}
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Executável removido após análise antivírus. Pacote NÃO aprovado."
}

$hashes= @(
    Get-FileHash -LiteralPath $exe -Algorithm SHA256
    Get-FileHash -LiteralPath $archive -Algorithm SHA256
)
$manifest=@()
foreach($item in $hashes) {
    $manifest+=("$($item.Hash.ToLowerInvariant())  $(Split-Path -Leaf $item.Path)")
}
$manifest | Set-Content -LiteralPath (Join-Path $report "SHA256SUMS.txt") -Encoding ascii
$securityReport=[ordered]@{
    schema=1
    project="DUELTRACE-WebUI"
    source_commit=$env:GITHUB_SHA
    defender_antivirus_enabled=$status.AntivirusEnabled
    defender_service_enabled=$status.AMServiceEnabled
    defender_signature_version=$status.AntivirusSignatureVersion
    defender_signature_age_days=$status.AntivirusSignatureAge
    scan_finished_utc=[DateTime]::UtcNow.ToString("o")
    scan_result="no_threat_detected"
    exe_sha256=$hashes[0].Hash.ToLowerInvariant()
    zip_sha256=$hashes[1].Hash.ToLowerInvariant()
    signed_code=$false
    guarantee_of_safety=$false
}
$securityReport | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $report "SECURITY-REPORT.json") -Encoding utf8
Write-Host "Análise antivírus concluída (sem achados conhecidos). Pacote permanece NÃO ASSINADO."
Write-Host "SHA-256 ZIP: $($hashes[1].Hash)"
