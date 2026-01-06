# monitor_walk_forward.ps1
# Run: .\monitor_walk_forward.ps1
# Stop: Ctrl+C

$ErrorActionPreference = "Stop"
$intervalSec = 5
$minWorkingSetGB = 1.0

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Walk-Forward Analysis Monitor" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$prevCpu = @{}  # pid -> cpu seconds
$cores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

$iteration = 0
while ($true) {
    $iteration++
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    Write-Host "========================================" -ForegroundColor Gray
    Write-Host "[$timestamp] Monitor #$iteration" -ForegroundColor Gray
    Write-Host "========================================" -ForegroundColor Gray

    # Python processes
    $procs = Get-Process -Name python -ErrorAction SilentlyContinue |
        Where-Object { ($_.WorkingSet64 / 1GB) -ge $minWorkingSetGB }

    if ($procs) {
        Write-Host ""
        Write-Host "Python processes (WorkingSet >= $minWorkingSetGB GB):" -ForegroundColor Cyan

        $rows = foreach ($p in $procs) {
            $processId = $p.Id
            $wsGB = [math]::Round($p.WorkingSet64 / 1GB, 2)

            $cpuSec = $p.CPU
            if ($null -eq $cpuSec) { $cpuSec = 0 }

            $cpuPct = 0.0
            if ($prevCpu.ContainsKey($processId)) {
                $delta = $cpuSec - $prevCpu[$processId]
                if ($delta -lt 0) { $delta = 0 }
                # CPU% ≈ (delta_cpu_seconds / interval) / cores * 100
                $cpuPct = [math]::Round((($delta / $intervalSec) / $cores) * 100, 1)
            }
            $prevCpu[$processId] = $cpuSec

            [pscustomobject]@{
                Id         = $processId
                MemoryGB   = $wsGB
                CpuPct     = $cpuPct
                StartTime  = $p.StartTime
            }
        }

        $rows | Sort-Object MemoryGB -Descending | Format-Table -AutoSize

        $sumGB = [math]::Round(($procs | Measure-Object -Property WorkingSet64 -Sum).Sum / 1GB, 2)
        Write-Host "Total Python WorkingSet: $sumGB GB" -ForegroundColor Yellow
    }
    else {
        Write-Host ""
        Write-Host "No Python process found (>= $minWorkingSetGB GB WorkingSet)." -ForegroundColor Yellow
    }

    # System memory
    $os = Get-CimInstance Win32_OperatingSystem
    $totalGB = $os.TotalVisibleMemorySize / 1MB
    $freeGB  = $os.FreePhysicalMemory / 1MB
    $usedGB  = $totalGB - $freeGB
    $memPct  = [math]::Round(($usedGB / $totalGB) * 100, 1)

    Write-Host ""
    Write-Host "System memory:" -ForegroundColor Cyan
    Write-Host ("  Used: {0} GB / {1} GB ({2}%)" -f ([math]::Round($usedGB,2)), ([math]::Round($totalGB,2)), $memPct) -ForegroundColor White

    if ($memPct -gt 90) {
        Write-Host "  WARNING: System memory usage > 90%" -ForegroundColor Red
    } elseif ($memPct -gt 80) {
        Write-Host "  CAUTION: System memory usage > 80%" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Next update in $intervalSec seconds..." -ForegroundColor Gray
    Write-Host ""

    Start-Sleep -Seconds $intervalSec
}
