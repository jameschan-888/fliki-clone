# 备份 → 在 [mcp_servers.headroom] 后补 enabled + startup_timeout_sec
$cfg = 'C:\Users\chanl\.codex\config.toml'
$bak = "$cfg.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $cfg -Destination $bak -Force
Write-Output "backup -> $bak"
$utf8 = New-Object System.Text.UTF8Encoding($true)
$lines = [System.IO.File]::ReadAllLines($cfg, $utf8)
$out = New-Object System.Collections.Generic.List[string]
$inHeadroom = $false
$patched = $false
for ($i = 0; $i -lt $lines.Length; $i++) {
    $l = $lines[$i]
    if ($l -match '^\[mcp_servers\.headroom\]') { $inHeadroom = $true; $out.Add($l); continue }
    if ($inHeadroom -and $l -match '^\[') { $inHeadroom = $false }
    if ($inHeadroom -and $l -match '^\s*args\s*=') {
        $out.Add($l)
        if (-not $patched) {
            $out.Add('enabled = true')
            $out.Add('startup_timeout_sec = 60')
            $out.Add('tool_timeout_sec = 60')
            $patched = $true
        }
        continue
    }
    $out.Add($l)
}
[System.IO.File]::WriteAllLines($cfg, $out, $utf8)
Write-Output "patched=$patched"