$ErrorActionPreference = "Stop"

$ruleName = "BLACK BOX UDP RTP H264 Camera 5600"

$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall rule already exists: $ruleName"
    return
}

New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol UDP `
    -LocalPort 5600 `
    -Profile Any | Out-Null

Write-Host "Firewall rule added: UDP 5600 inbound allowed."
