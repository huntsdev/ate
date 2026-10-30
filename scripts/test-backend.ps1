# Disposable PostgreSQL for the complete backend suite; never uses application volumes.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'docker.ps1')
$dockerExecutable = Initialize-DockerCli
$uvExecutable = (Get-Command uv -CommandType Application -ErrorAction Stop).Source
$repoRoot = Split-Path $PSScriptRoot -Parent
$testContainer = 'ate-tests-' + [guid]::NewGuid().ToString('N')
$composeText = [IO.File]::ReadAllText((Join-Path $repoRoot 'compose.yaml'))
$imageMatch = [regex]::Match($composeText, '(?m)^\s+image: (pgvector/pgvector:\S+)\s*$')
if (-not $imageMatch.Success) { throw 'Pinned PostgreSQL image not found in compose.yaml.' }
$postgresImage = $imageMatch.Groups[1].Value
$previousTestUrl = $env:ATE_TEST_DATABASE_URL
$containerCreated = $false
try {
    & $dockerExecutable run --rm -d --name $testContainer -p '127.0.0.1::5432' `
        -e POSTGRES_USER=ate_test -e POSTGRES_PASSWORD=synthetic-disposable-test-password `
        -e POSTGRES_DB=ate_test --health-cmd 'pg_isready -U ate_test -d ate_test' `
        --health-interval 1s --health-timeout 3s --health-retries 30 $postgresImage | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not start disposable PostgreSQL.' }
    $containerCreated = $true
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        $health = & $dockerExecutable inspect --format '{{.State.Health.Status}}' $testContainer
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect test PostgreSQL.' }
        if ($health -eq 'healthy') { break }
        if ($health -eq 'unhealthy' -or [DateTime]::UtcNow -gt $deadline) {
            throw 'Disposable PostgreSQL failed readiness.'
        }
        Start-Sleep -Seconds 1
    } while ($true)
    $publishedPort = & $dockerExecutable port $testContainer 5432/tcp
    if ($LASTEXITCODE -ne 0 -or $publishedPort -notmatch '^127\.0\.0\.1:(\d+)$') {
        throw 'Expected a loopback-only disposable PostgreSQL port.'
    }
    $env:ATE_TEST_DATABASE_URL = "postgresql://ate_test:synthetic-disposable-test-password@127.0.0.1:$($Matches[1])/ate_test"
    Push-Location (Join-Path $repoRoot 'apps/api')
    try {
        & $uvExecutable run --locked python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
    }
    finally { Pop-Location }
}
finally {
    $env:ATE_TEST_DATABASE_URL = $previousTestUrl
    if ($containerCreated) {
        & $dockerExecutable stop --timeout 10 $testContainer | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning "Could not stop disposable container $testContainer." }
    }
}
