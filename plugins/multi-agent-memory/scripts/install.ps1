<#
.SYNOPSIS
  Install multi-agent-memory CLI + link Skill into host skill directories.

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Hosts claude,cursor,deepseek,opencode,qoder -SkipPip
#>
[CmdletBinding()]
param(
  [string[]] $Hosts = @("claude", "cursor", "deepseek", "opencode", "qoder"),
  [switch] $SkipPip,
  [switch] $ProjectAgents,
  [switch] $ProjectCursor,
  [switch] $ProjectQoder,
  [switch] $CursorHooks
)

$ErrorActionPreference = "Stop"
$PluginRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SkillSrc = Join-Path $PluginRoot "skills\multi-agent-memory"
$RepoRoot = Resolve-Path (Join-Path $PluginRoot "..\..")

if (-not (Test-Path (Join-Path $SkillSrc "SKILL.md"))) {
  throw "Skill not found: $SkillSrc"
}

# 支持 -Hosts claude,cursor 或 -Hosts @('claude','cursor')
$normalized = @()
foreach ($h in $Hosts) {
  foreach ($part in ($h -split '[,;\s]+')) {
    $name = $part.Trim().ToLowerInvariant()
    if ($name) { $normalized += $name }
  }
}
$normalized = $normalized | Select-Object -Unique

function New-SkillLink {
  param([string] $Destination)
  $parent = Split-Path -Parent $Destination
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  if (Test-Path $Destination) {
    $item = Get-Item $Destination -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      cmd /c "rmdir `"$Destination`"" | Out-Null
    } else {
      Remove-Item -LiteralPath $Destination -Recurse -Force
    }
  }
  $result = cmd /c "mklink /J `"$Destination`" `"$SkillSrc`"" 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "junction failed ($Destination): $result ; falling back to copy"
    Copy-Item -Path $SkillSrc -Destination $Destination -Recurse -Force
  } else {
    Write-Host "linked $Destination"
  }
}

$py = $null
if (-not $SkipPip) {
  Write-Host "Installing Python package from $PluginRoot ..."
  foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
      $py = $candidate
      break
    }
  }
  if (-not $py) { throw "Neither python, python3, nor py found on PATH" }
  if ($py -eq "py") {
    & $py -3 -m pip install --upgrade $PluginRoot
  } else {
    & $py -m pip install --upgrade $PluginRoot
  }
}

$map = @{
  claude   = @(Join-Path $env:USERPROFILE ".claude\skills\multi-agent-memory")
  cursor   = @(Join-Path $env:USERPROFILE ".cursor\skills\multi-agent-memory")
  deepseek = @(Join-Path $env:USERPROFILE ".agents\skills\multi-agent-memory")
  opencode = @(
    (Join-Path $env:USERPROFILE ".agents\skills\multi-agent-memory"),
    (Join-Path $env:USERPROFILE ".opencode\skills\multi-agent-memory")
  )
  qoder    = @(Join-Path $env:USERPROFILE ".qoder\skills\multi-agent-memory")
}
$known = "claude,cursor,deepseek,opencode,qoder,codex"

foreach ($h in $normalized) {
  if ($h -eq "codex") {
    Write-Host "Codex: use marketplace (codex plugin add multi-agent-memory@multi-agent-memory); Skill ships in plugin."
    continue
  }
  if (-not $map.ContainsKey($h)) {
    Write-Warning "Unknown host '$h' (known: $known)"
    continue
  }
  foreach ($dst in $map[$h]) {
    New-SkillLink -Destination $dst
  }
}

if ($ProjectAgents) {
  $proj = Join-Path $RepoRoot ".agents\skills\multi-agent-memory"
  New-SkillLink -Destination $proj
}
if ($ProjectCursor) {
  $projC = Join-Path $RepoRoot ".cursor\skills\multi-agent-memory"
  New-SkillLink -Destination $projC
}
if ($ProjectQoder) {
  $projQ = Join-Path $RepoRoot ".qoder\skills\multi-agent-memory"
  New-SkillLink -Destination $projQ
}

if (-not $py) {
  foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
      $py = $candidate
      break
    }
  }
}

if ($CursorHooks) {
  $hooksSrc = Join-Path $PluginRoot "adapters\cursor\hooks"
  $hooksJsonSrc = Join-Path $PluginRoot "adapters\cursor\hooks.json"
  $hooksDst = Join-Path $RepoRoot ".cursor\hooks"
  New-Item -ItemType Directory -Force -Path $hooksDst | Out-Null
  Copy-Item -Path (Join-Path $hooksSrc "*.py") -Destination $hooksDst -Force
  $hooksJsonDst = Join-Path $RepoRoot ".cursor\hooks.json"
  $pyCmd = if ($py) { if ($py -eq "py") { "py -3" } else { $py } } else { "python" }
  $jsonText = Get-Content -Raw -Path $hooksJsonSrc
  if ($pyCmd -eq "python3") {
    $jsonText = $jsonText -replace '"command": "python ', '"command": "python3 '
  }
  Set-Content -Path $hooksJsonDst -Value $jsonText -Encoding utf8
  Write-Host "installed Cursor hooks -> $hooksDst and $hooksJsonDst (interpreter: $pyCmd)"
}

Write-Host ""
Write-Host "Done. Verify:"
Write-Host "  python -c `"import multi_agent_memory as m; print(m.__version__)`""
Write-Host "  memory-hub doctor"
Write-Host "  memory-hub sync --check"
Write-Host "Agent short names: claude | codex | cursor | deepseek | opencode | qoder"
Write-Host "Shared workflow: $PluginRoot\adapters\shared-workflow.md"
Write-Host "Cross-platform:  $PluginRoot\adapters\cross-platform.md"
Write-Host "Adapters: $PluginRoot\adapters\README.md"
Write-Host "Optional Cursor hooks: install.ps1 -CursorHooks"
Write-Host ""
Write-Host "Companions (detect only, never auto-installed):"
try {
  if (-not $py) { throw "no python" }
  $pyArgs = @("-c", "from multi_agent_memory.hub import probe_companions; import json; print(json.dumps(probe_companions(), ensure_ascii=False))")
  if ($py -eq "py") { $pyArgs = @("-3") + $pyArgs }
  $probe = & $py @pyArgs 2>$null
  if ($LASTEXITCODE -eq 0 -and $probe) {
    $obj = $probe | ConvertFrom-Json
    Write-Host ("  gitnexus: " + $obj.gitnexus.status + " — " + $obj.gitnexus.role)
    Write-Host ("  aoci:     " + $obj.aoci.status + " — " + $obj.aoci.role)
    Write-Host "  Install yourself if needed; see adapters/shared-workflow.md"
  } else {
    Write-Host "  (probe skipped — run: memory-hub doctor)"
  }
} catch {
  Write-Host "  (probe skipped — run: memory-hub doctor)"
}
