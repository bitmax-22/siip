Param(
    [string]$RepoPath = "C:\Users\Administrator\Desktop\SIIP CON FOTO",
    [string]$Branch = "master",
    [string]$LogPath = "C:\Users\Administrator\Desktop\SIIP_CON_FOTO_git_backup.log"
)

try {
    if (-not (Test-Path $RepoPath)) {
        throw "La ruta del repositorio no existe: $RepoPath"
    }

    Set-Location -Path $RepoPath

    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $status = git status --porcelain

    if ([string]::IsNullOrWhiteSpace($status)) {
        $message = "$timestamp - Sin cambios pendientes, no se generó commit."
    }
    else {
        git add -A | Out-Null
        $commitMessage = "chore: respaldo automático $timestamp"
        git commit -m $commitMessage | Out-Null
        git push origin $Branch | Out-Null
        $message = "$timestamp - Respaldo automático completado y enviado a '$Branch'."
    }
}
catch {
    $message = "$timestamp - Error en respaldo automático: $_"
}
finally {
    if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
        $message | Out-File -FilePath $LogPath -Append -Encoding UTF8
    }
}

