param(
    [string]$Url = "https://nexora-defi-dev.onrender.com/health/live",
    [int]$IntervalSeconds = 300
)

Write-Host "Keeping Render service awake: $Url"
Write-Host "Ping interval: $IntervalSeconds seconds"

while ($true) {
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
        Write-Host "$timestamp status=$($response.StatusCode)"
    }
    catch {
        Write-Host "$timestamp error=$($_.Exception.Message)"
    }
    Start-Sleep -Seconds $IntervalSeconds
}
