<#
.SYNOPSIS
  Install multi-agent-memory CLI + link Skill into host skill directories.

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Hosts claude,cursor,deepseek,opencode -SkipPip
#>
[CmdletBinding()]
param(
  [string[]] $Hosts = @("claude", "cursor", "deepseek", "opencode"),
  [switch] $SkipPip,
  [switch] $ProjectAgents
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

if (-not $SkipPip) {
  Write-Host "Installing Python package from $PluginRoot ..."
  python -m pip install --upgrade $PluginRoot
}

$map = @{
  claude   = @(Join-Path $env:USERPROFILE ".claude\skills\multi-agent-memory")
  cursor   = @(Join-Path $env:USERPROFILE ".cursor\skills\multi-agent-memory")
  deepseek = @(Join-Path $env:USERPROFILE ".agents\skills\multi-agent-memory")
  opencode = @(
    (Join-Path $env:USERPROFILE ".agents\skills\multi-agent-memory"),
    (Join-Path $env:USERPROFILE ".opencode\skills\multi-agent-memory")
  )
}

foreach ($h in $normalized) {
  if ($h -eq "codex") {
    Write-Host "Codex: use marketplace (codex plugin add multi-agent-memory@multi-agent-memory); Skill ships in plugin."
    continue
  }
  if (-not $map.ContainsKey($h)) {
    Write-Warning "Unknown host '$h' (known: claude,cursor,deepseek,opencode,codex)"
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

Write-Host ""
Write-Host "Done. Verify:"
Write-Host "  python -c `"import multi_agent_memory as m; print(m.__version__)`""
Write-Host "  memory-hub doctor"
Write-Host "Agent short names: claude | codex | cursor | deepseek | opencode"
Write-Host "Adapters: $PluginRoot\adapters\README.md"
