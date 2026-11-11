#requires -Version 5.1
<#
Manual promotion of a previously CI-validated PRIVATE Windows Preview to a
PUBLIC, binary-only customer release. Fail closed: no source repo publication,
no unsigned EXE, no disabled Microsoft Defender, no package replacement,
no tokens embedded in binaries or logged to output.
#>
param([Parameter(Mandatory=$true)][string]$PrivateTag)
$ErrorActionPreference="Stop"
$privateRepo="guibatoni/appassist"
$publicRepo="guibatoni/dueltrace-releases"
$assetName="DUELTRACE-WebUI-Windows-Preview.zip"

if ($PrivateTag -cnotmatch '^preview-v(?<version>\d{1,4}\.\d{1,4}\.\d{1,4})-r(?<build>[1-9]\d{0,14})$') {
    throw "Tag de compilação inválida."
}
$version=$Matches.version
$runId=[long]$Matches.build
if (!$env:PRIVATE_GH_TOKEN -or !$env:PUBLIC_GH_TOKEN) {
    throw "Autorização de publicação não configurada."
}
if (!$env:PFX_BASE64 -or !$env:PFX_PASSWORD -or !$env:EXPECTED_PUBLISHER) {
    throw "A distribuição pública exige certificado Authenticode e editor verificado."
}
$env:GH_TOKEN=$env:PRIVATE_GH_TOKEN
$release=gh api "repos/$privateRepo/releases/tags/$PrivateTag" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or !$release -or $release.draft -or !$release.prerelease) {
    throw "Pré-release privada ausente ou não aprovada."
}
$sha=$release.target_commitish
if ($sha -cnotmatch '^[a-f0-9]{40}$') {
    throw "SHA de origem privada inválido."
}
$assets=@($release.assets | Where-Object { $_.name -eq $assetName })
if ($assets.Count -ne 1 -or $assets[0].size -lt 1000000 -or
    $assets[0].size -gt 230MB -or
    $assets[0].digest -cnotmatch '^sha256:[a-f0-9]{64}$') {
    throw "Asset privado sem hash/tamanho auditado."
}
$expected=$assets[0].digest.Substring(7)
$footer="Build $runId | Commit $sha | SHA-256 ZIP: $expected"
if (![string]::IsNullOrEmpty($release.body) -and !$release.body.Contains($footer)) {
    throw "Notas oficiais não correspondem ao ZIP assinado."
}
if ([string]::IsNullOrEmpty($release.body)) {
    throw "Notas oficiais sem identidade de build."
}
$run=gh api "repos/$privateRepo/actions/runs/$runId" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or !$run -or $run.status -ne 'completed' -or
    $run.conclusion -ne 'success' -or $run.event -ne 'push' -or
    $run.head_sha -cne $sha) {
    throw "O build privado não concluiu os testes Windows."
}

New-Item -ItemType Directory -Force -Path private-update | Out-Null
gh release download $PrivateTag --repo $privateRepo --pattern $assetName --dir private-update
if ($LASTEXITCODE -ne 0) { throw "Falha ao obter release privada." }
$originalZip=(Resolve-Path "private-update/$assetName").Path
if ((Get-FileHash -LiteralPath $originalZip -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected -or
    (Get-Item $originalZip).Length -ne $assets[0].size) {
    throw "Conteúdo privado difere do SHA-256 publicado."
}

# Reuse the same defensive extraction and embedded manifest checks
# performed on client computers; do NOT use Expand-Archive on untrusted ZIP.
$env:PYTHONPATH=(Join-Path (Get-Location).Path "scanner")
$env:PRIVATE_ZIP=$originalZip
$env:PRIVATE_VERSION=$version
$env:PRIVATE_RUN="$runId"
$env:PRIVATE_SHA=$sha
$validation=@'
import os
from pathlib import Path
from dueltrace_preview_installer import unpack_preview_zip
unpack_preview_zip(
    Path(os.environ["PRIVATE_ZIP"]),
    Path("customer-package"),
    {"version":os.environ["PRIVATE_VERSION"],
     "run_id":int(os.environ["PRIVATE_RUN"]),
     "sha":os.environ["PRIVATE_SHA"]},
)
'@
$validation | python -
if ($LASTEXITCODE -ne 0) { throw "Identidade do ZIP privado rejeitada." }

# The signing key is used once on the hosted runner, never copied to output.
$pfx=Join-Path $env:RUNNER_TEMP "dueltrace-temporary-signing.pfx"
try {
    [IO.File]::WriteAllBytes($pfx,[Convert]::FromBase64String($env:PFX_BASE64))
    $sdk=Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
    $signTool=Get-ChildItem -LiteralPath $sdk -Recurse -File -Filter "signtool.exe" |
        Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (!$signTool) { throw "signtool.exe não encontrado no runner Windows." }
    & $signTool sign /fd SHA256 /f $pfx /p $env:PFX_PASSWORD /tr http://timestamp.digicert.com /td SHA256 "customer-package/DUELTRACE-WebUI.exe"
    if ($LASTEXITCODE -ne 0) { throw "Assinatura digital não concluída." }
} finally {
    Remove-Item -LiteralPath $pfx -Force -ErrorAction SilentlyContinue
}
Remove-Item "customer-package/LEIA-ME-SEGURANCA.txt" -ErrorAction SilentlyContinue
Copy-Item "tools/security/AVISO-ATUALIZACAO-CLIENTES.txt" "customer-package/LEIA-ME-ATUALIZACAO.txt"
New-Item -ItemType Directory -Force -Path public-update | Out-Null
$publicZip="public-update/$assetName"
Compress-Archive -Path "customer-package/*" -DestinationPath $publicZip -Force
python tools/security/audit_windows_archive.py customer-package $publicZip --report public-update/archive-integrity.json
if ($LASTEXITCODE -ne 0) { throw "Falha na auditoria do ZIP público." }
./tools/security/gate_windows_package.ps1 -PackageDirectory customer-package -ZipPath $publicZip -OutputDirectory public-update/security -RequireSignature -ExpectedPublisherSubject $env:EXPECTED_PUBLISHER

# The public GitHub token may access ONLY the destination release repository.
$env:GH_TOKEN=$env:PUBLIC_GH_TOKEN
$public=gh api "repos/$publicRepo" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or !$public -or $public.private -or
    $public.full_name -cne $publicRepo) {
    throw "Repositório de atualizações público não configurado."
}
# gh release create is create-only: existing tags are never overwritten.
$zip=(Resolve-Path $publicZip).Path
$digest=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
$notes=(Get-Content "docs/DUELTRACE_UPDATE_NOTES.md" -Raw -Encoding UTF8).Trim()
$notes+=[Environment]::NewLine+[Environment]::NewLine+"Pacote Windows assinado para clientes. Somente executável; código-fonte privado não publicado."
$notes+=[Environment]::NewLine+[Environment]::NewLine+"Build $runId | Commit $sha | SHA-256 ZIP: $digest"
$notesFile=Join-Path $env:RUNNER_TEMP "dueltrace-public-notes.md"
Set-Content -LiteralPath $notesFile -Value $notes -Encoding UTF8
gh release create $PrivateTag $zip --repo $publicRepo --target main --title "DUELTRACE v$version Windows - atualização" --notes-file $notesFile --prerelease --latest=false
if ($LASTEXITCODE -ne 0) { throw "Publicação da release não concluída." }

$posted=gh api "repos/$publicRepo/releases/tags/$PrivateTag" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or !$posted -or $posted.draft) {
    throw "Release pública não ficou disponível."
}
$published=@($posted.assets | Where-Object { $_.name -eq $assetName })
if ($published.Count -ne 1 -or $published[0].digest -cne "sha256:$digest" -or
    $published[0].size -ne (Get-Item $zip).Length) {
    throw "Digest/tamanho da publicação não corresponde ao ZIP aprovado."
}
Write-Host "Distribuição Windows verificada, aprovada e publicada."
