<#
.SYNOPSIS
    Authenticode-sign the YaskawaTools Windows executable.

.DESCRIPTION
    Signs the built .exe with a code-signing certificate and applies an RFC-3161
    timestamp so the signature stays valid after the certificate expires.
    Signing gives the binary integrity (tamper-evidence) and removes the
    SmartScreen "unknown publisher" warning, closing the gap that a purely
    client-side password check cannot.

    Provide the certificate either by store thumbprint (-Thumbprint) or by a
    PFX file (-PfxPath / -PfxPassword). Never commit a PFX or its password.

.EXAMPLE
    # Using a certificate already installed in the user's store:
    .\scripts\sign_windows.ps1 -Thumbprint 'A1B2C3...'

.EXAMPLE
    # Using a PFX file (password prompted securely if omitted):
    .\scripts\sign_windows.ps1 -PfxPath C:\keys\codesign.pfx
#>
[CmdletBinding(DefaultParameterSetName = 'Store')]
param(
    [string] $ExePath = "$PSScriptRoot\..\dist\Melo\YaskawaTools.exe",

    [Parameter(ParameterSetName = 'Store', Mandatory = $true)]
    [string] $Thumbprint,

    [Parameter(ParameterSetName = 'Pfx', Mandatory = $true)]
    [string] $PfxPath,
    [Parameter(ParameterSetName = 'Pfx')]
    [System.Security.SecureString] $PfxPassword,

    [string] $TimestampUrl = 'http://timestamp.digicert.com'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $ExePath)) {
    throw "Executable not found: $ExePath  (build it first)"
}

# Locate signtool.exe from the Windows SDK.
$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
    $candidate = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match 'x64' } |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $candidate) { throw 'signtool.exe not found. Install the Windows 10/11 SDK.' }
    $signtool = $candidate.FullName
} else {
    $signtool = $signtool.Source
}

$common = @('sign', '/fd', 'SHA256', '/tr', $TimestampUrl, '/td', 'SHA256', '/v')

if ($PSCmdlet.ParameterSetName -eq 'Store') {
    $args = $common + @('/sha1', $Thumbprint, $ExePath)
} else {
    if (-not (Test-Path $PfxPath)) { throw "PFX not found: $PfxPath" }
    if (-not $PfxPassword) { $PfxPassword = Read-Host -AsSecureString 'PFX password' }
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPassword))
    $args = $common + @('/f', $PfxPath, '/p', $plain, $ExePath)
}

Write-Host "Signing $ExePath ..." -ForegroundColor Cyan
& $signtool @args
if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }

Write-Host 'Verifying signature ...' -ForegroundColor Cyan
& $signtool verify /pa /v $ExePath
if ($LASTEXITCODE -ne 0) { throw "Signature verification failed ($LASTEXITCODE)" }

Write-Host 'Done: executable signed and timestamped.' -ForegroundColor Green
