# Installs five Claude Code animation skills at user level (available in every project):
#   Three.js       CloudAI-X/threejs-skills         -> ~\.claude\skills\threejs-*
#   GSAP           greensock/gsap-skills            -> plugin gsap-skills@gsap-skills
#   Design DNA     zanwei/design-dna                -> ~\.claude\skills\design-dna
#   Motion Design  LottieFiles/motion-design-skill  -> ~\.claude\skills\motion-design
#   Genjutsu       AThevon/genjutsu                 -> plugin genjutsu@genjutsu
#
# Usage:  powershell -ExecutionPolicy Bypass -File install.ps1           # audited commits pinned below
#         powershell -ExecutionPolicy Bypass -File install.ps1 -Latest   # newest commits instead (not audited)
# Piped:  irm <url>/install.ps1 | iex                                    # pinned commits only
#
# Re-running is safe: skill folders are replaced, plugins already present are kept.
# Works in Windows PowerShell 5.1 and PowerShell 7+.
param([switch]$Latest)

# Run in a child scope so that 'irm | iex' does not leave settings or helpers in the caller's session.
& {
    $ErrorActionPreference = 'Stop'

    # Commits reviewed on 2026-10-19 (no hooks, no MCP servers, no hidden instructions).
    $ThreejsSha = '0e181866f095b5f06d005133876e926515390d95'
    $DesignDnaSha = '593e39bc9e3652734653bd75544a333d7d43615e'
    $MotionDesignSha = 'f9a8a041b85185ee4881b3471d3415e939aac772'

    # Native commands do not throw on failure, so check the exit code ourselves.
    function Invoke-Native {
        param([string]$Exe, [string[]]$Arguments)
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed (exit code $LASTEXITCODE)" }
    }

    # Shallow checkout of the pinned commit (or the default branch with -Latest).
    function Get-Repo {
        param([string]$Repo, [string]$Sha, [string]$Dest)
        if ($Latest) {
            Invoke-Native git @('clone', '-q', '--depth', '1', "https://github.com/$Repo", $Dest)
        } else {
            Invoke-Native git @('init', '-q', $Dest)
            Invoke-Native git @('-C', $Dest, 'fetch', '-q', '--depth', '1', "https://github.com/$Repo", $Sha)
            Invoke-Native git @('-C', $Dest, 'checkout', '-q', 'FETCH_HEAD')
        }
    }

    # Replace <skills>\<Name> with a copy of <Src>.
    function Install-SkillDir {
        param([string]$Src, [string]$Name)
        $dst = Join-Path $SkillsDir $Name
        if (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst -Recurse -Force }
        Copy-Item -LiteralPath $Src -Destination $dst -Recurse -Force
        $git = Join-Path $dst '.git'
        if (Test-Path -LiteralPath $git) { Remove-Item -LiteralPath $git -Recurse -Force }
        Write-Host "    + $Name"
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'git is required: https://git-scm.com/download/win'
    }

    $ConfigDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
    $SkillsDir = Join-Path $ConfigDir 'skills'
    New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null
    $Tmp = Join-Path ([IO.Path]::GetTempPath()) ('claude-skills-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

    try {
        Write-Host "Skills folder: $SkillsDir"

        Write-Host '==> Three.js'
        Get-Repo 'CloudAI-X/threejs-skills' $ThreejsSha (Join-Path $Tmp 'threejs')
        Get-ChildItem -LiteralPath (Join-Path $Tmp 'threejs\skills') -Directory | ForEach-Object {
            Install-SkillDir $_.FullName $_.Name
        }

        Write-Host '==> Design DNA'
        Get-Repo 'zanwei/design-dna' $DesignDnaSha (Join-Path $Tmp 'design-dna')
        Install-SkillDir (Join-Path $Tmp 'design-dna') 'design-dna'

        Write-Host '==> Motion Design'
        Get-Repo 'LottieFiles/motion-design-skill' $MotionDesignSha (Join-Path $Tmp 'motion-design')
        Install-SkillDir (Join-Path $Tmp 'motion-design\skills\motion-design') 'motion-design'
    } finally {
        Remove-Item -LiteralPath $Tmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # GSAP and Genjutsu ship as Claude Code plugins, so they go through the plugin marketplace.
    # Prefer claude.exe / claude.cmd: claude.ps1 can be blocked by the execution policy.
    $plugins = @(
        @{ Source = 'greensock/gsap-skills'; Id = 'gsap-skills@gsap-skills' },
        @{ Source = 'AThevon/genjutsu'; Id = 'genjutsu@genjutsu' }
    )
    $claude = Get-Command claude.exe, claude.cmd, claude -CommandType Application, ExternalScript -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $failed = @()
    if ($claude) {
        foreach ($p in $plugins) {
            Write-Host "==> plugin $($p.Id)"
            try {
                Invoke-Native $claude.Source @('plugin', 'marketplace', 'add', $p.Source)
                Invoke-Native $claude.Source @('plugin', 'install', $p.Id)
            } catch {
                Write-Host $_ -ForegroundColor Red
                $failed += $p
            }
        }
    } else {
        Write-Host ''
        Write-Host "!! 'claude' was not found in PATH, so the GSAP and Genjutsu plugins were not installed." -ForegroundColor Yellow
        $failed = $plugins
    }

    if ($failed.Count -gt 0) {
        Write-Host ''
        Write-Host '!! Install these plugins inside Claude Code instead:' -ForegroundColor Yellow
        foreach ($p in $failed) {
            Write-Host "     /plugin marketplace add $($p.Source)"
            Write-Host "     /plugin install $($p.Id)"
        }
    }

    Write-Host ''
    Write-Host 'Done. Restart Claude Code (or open a new session) to load the skills.'
    Write-Host 'Try: /genjutsu:cast, /motion-design, /design-dna, /threejs-fundamentals, /gsap-skills:gsap-core'
}
