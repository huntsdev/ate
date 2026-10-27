# Runs against the local Compose development stack only; recreates containers.
param([switch]$Elastic)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'docker.ps1')
$dockerExecutable = Initialize-DockerCli
$repoRoot = Split-Path $PSScriptRoot -Parent
$testToken = [guid]::NewGuid().ToString('N')
$testIndex = "ate-phase0-probe-$testToken"
$composeArguments = @('compose', '--project-directory', $repoRoot, '-f', (Join-Path $repoRoot 'compose.yaml'))
if ($Elastic) { $composeArguments += @('--profile', 'elastic') }

function Invoke-Compose {
    param([string[]]$ComposeCommand)
    & $dockerExecutable @composeArguments @ComposeCommand
    if ($LASTEXITCODE -ne 0) { throw "Compose command failed: $($ComposeCommand[0])" }
}

$databasePrepared = $false
$elasticPrepared = $false
try {
    Invoke-Compose @('up', '--build', '-d', '--wait', '--wait-timeout', '300')
    Invoke-Compose @('exec', '-T', 'api', 'python', '-m', 'sentinelforge.persistence_probe', 'prepare', $testToken)
    $databasePrepared = $true
    if ($Elastic) {
        Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:9200/$testIndex/_doc/1?refresh=true" -ContentType 'application/json' -Body ('{"synthetic":true,"token":"' + $testToken + '"}') | Out-Null
        $elasticPrepared = $true
    }
    Invoke-Compose @('down', '--timeout', '30')
    Invoke-Compose @('up', '-d', '--wait', '--wait-timeout', '300')
    Invoke-Compose @('exec', '-T', 'api', 'python', '-m', 'sentinelforge.persistence_probe', 'verify', $testToken)
    if ($Elastic) {
        $document = Invoke-RestMethod -Uri "http://127.0.0.1:9200/$testIndex/_doc/1"
        if ($document._source.token -ne $testToken) { throw 'Synthetic telemetry did not survive restart.' }
    }
    Invoke-Compose @('exec', '-T', 'api', 'python', '-m', 'sentinelforge.smoke')
    Write-Output 'PASS: synthetic data survived Compose down/up. Named volumes were preserved.'
}
finally {
    if ($databasePrepared) {
        & $dockerExecutable @composeArguments exec -T api python -m sentinelforge.persistence_probe cleanup $testToken
        if ($LASTEXITCODE -ne 0) { Write-Warning "Cleanup incomplete; retry cleanup for token $testToken after restoring the stack." }
    }
    if ($elasticPrepared) {
        try { Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:9200/$testIndex" | Out-Null }
        catch { Write-Warning "Cleanup incomplete; remove only the synthetic index $testIndex after restoring Elastic." }
    }
}
