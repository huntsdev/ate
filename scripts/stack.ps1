param(
    [ValidateSet('Start', 'Stop', 'Restart', 'Status', 'Logs', 'Migrate', 'Smoke', 'Validate')]
    [string]$Action = 'Status',
    [switch]$Dev,
    [switch]$Elastic
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'docker.ps1')
$dockerExecutable = Initialize-DockerCli
$repoRoot = Split-Path $PSScriptRoot -Parent
$composeArguments = @('compose', '--project-directory', $repoRoot, '-f', (Join-Path $repoRoot 'compose.yaml'))
if ($Dev) { $composeArguments += @('-f', (Join-Path $repoRoot 'compose.dev.yaml')) }
if ($Elastic) { $composeArguments += @('--profile', 'elastic') }

function Invoke-Compose {
    param([string[]]$ComposeCommand)
    & $dockerExecutable @composeArguments @ComposeCommand
    if ($LASTEXITCODE -ne 0) { throw "Compose command failed: $($ComposeCommand[0])" }
}

switch ($Action) {
    'Start' { Invoke-Compose @('up', '--build', '-d', '--wait', '--wait-timeout', '300') }
    'Stop' { Invoke-Compose @('down', '--timeout', '30') }
    'Restart' {
        Invoke-Compose @('down', '--timeout', '30')
        Invoke-Compose @('up', '-d', '--wait', '--wait-timeout', '300')
    }
    'Status' { Invoke-Compose @('ps', '--all') }
    'Logs' { Invoke-Compose @('logs', '--tail', '100', 'api', 'worker', 'web') }
    'Migrate' { Invoke-Compose @('run', '--rm', '--no-deps', 'migrate') }
    'Smoke' {
        Invoke-Compose @('run', '--rm', '--no-deps', 'migrate')
        Invoke-Compose @('run', '--rm', '--no-deps', 'migrate')
        Invoke-Compose @('exec', '-T', 'api', 'python', '-m', 'sentinelforge.smoke')
    }
    'Validate' { Invoke-Compose @('config', '--quiet') }
}
