# Shared CLI discovery for Windows PowerShell and cross-platform pwsh.
function Initialize-DockerCli {
    $dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($dockerCommand) { return $dockerCommand.Source }

    $dockerCandidates = @()
    if ($env:LOCALAPPDATA) {
        $dockerCandidates += Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
        $dockerCandidates += Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\resources\bin\docker.exe'
    }
    if ($env:ProgramFiles) {
        $dockerCandidates += Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'
    }

    foreach ($dockerCandidate in $dockerCandidates) {
        if (Test-Path -LiteralPath $dockerCandidate -PathType Leaf) {
            # BuildKit may also need docker-credential-desktop from this directory.
            # Update this process only; leave the user's persistent PATH untouched.
            $dockerDirectory = Split-Path $dockerCandidate -Parent
            $env:PATH = $dockerDirectory + [System.IO.Path]::PathSeparator + $env:PATH
            return $dockerCandidate
        }
    }

    throw 'Docker CLI not found on PATH or in standard Docker Desktop locations. Install Docker Desktop or add its resources\bin directory to PATH, then reopen the terminal.'
}
