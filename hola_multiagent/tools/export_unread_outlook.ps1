param(
    [string]$OutputPath = "data/outlook_unread.csv",
    [string]$Mailbox = "",
    [switch]$AllFolders,
    [int]$MaxItems = 0
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectPath {
    param([string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return (Join-Path (Get-Location) $PathValue)
}

function Get-OutlookFolderPath {
    param($Folder)

    return (ConvertTo-CleanText $Folder.FolderPath)
}

function ConvertTo-CleanText {
    param($Value)

    if ($null -eq $Value) {
        return ""
    }
    return (($Value.ToString() -replace "\s+", " ").Trim())
}

function ConvertTo-CsvRow {
    param($MailItem, [string]$FolderPath)

    $cleanBody = ConvertTo-CleanText $MailItem.Body
    $senderEmail = ConvertTo-CleanText $MailItem.SenderEmailAddress
    if ($MailItem.SenderEmailType -eq "EX" -and $null -ne $MailItem.Sender) {
        try {
            $exchangeUser = $MailItem.Sender.GetExchangeUser()
            if ($null -ne $exchangeUser -and $exchangeUser.PrimarySmtpAddress) {
                $senderEmail = ConvertTo-CleanText $exchangeUser.PrimarySmtpAddress
            }
        }
        catch {
            $senderEmail = ConvertTo-CleanText $MailItem.SenderEmailAddress
        }
    }

    [PSCustomObject]@{
        message_id      = ConvertTo-CleanText $MailItem.EntryID
        thread_id       = ConvertTo-CleanText $MailItem.ConversationID
        date            = $MailItem.ReceivedTime
        from_name       = ConvertTo-CleanText $MailItem.SenderName
        from_email      = $senderEmail
        to              = ConvertTo-CleanText $MailItem.To
        cc              = ConvertTo-CleanText $MailItem.CC
        subject         = ConvertTo-CleanText $MailItem.Subject
        body            = $cleanBody
        snippet         = $cleanBody.Substring(0, [Math]::Min(240, $cleanBody.Length))
        is_read         = $false
        has_attachments = ($MailItem.Attachments.Count -gt 0)
        labels          = "unread; $FolderPath"
        source          = "outlook-desktop"
    }
}

function Export-UnreadFromFolder {
    param($Folder, [System.Collections.Generic.List[object]]$Rows)

    $folderPath = Get-OutlookFolderPath $Folder
    try {
        $items = $Folder.Items
        $items.Sort("[ReceivedTime]", $true)

        $unreadItems = $items.Restrict("[Unread] = true")
        foreach ($item in $unreadItems) {
            if ($MaxItems -gt 0 -and $Rows.Count -ge $MaxItems) {
                return
            }

            if ($item.MessageClass -like "IPM.Note*") {
                $Rows.Add((ConvertTo-CsvRow $item $folderPath))
            }
        }
    }
    catch {
        Write-Warning "No se pudo leer la carpeta ${folderPath}: $($_.Exception.Message)"
    }

    if ($AllFolders) {
        foreach ($subfolder in $Folder.Folders) {
            if ($MaxItems -gt 0 -and $Rows.Count -ge $MaxItems) {
                return
            }
            Export-UnreadFromFolder $subfolder $Rows
        }
    }
}

function Get-OutlookApplication {
    try {
        return [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application")
    }
    catch {
        try {
            return New-Object -ComObject Outlook.Application
        }
        catch {
            $detail = $_.Exception.Message
            throw @"
No se pudo iniciar Outlook por COM.

Causas probables:
1. Estas usando Nuevo Outlook. Este script requiere Outlook clasico de Windows.
2. Outlook clasico no esta instalado o no tiene un perfil configurado.
3. Outlook esta abierto como administrador y PowerShell no, o al reves. Ejecuta ambos sin administrador.
4. Outlook quedo colgado en segundo plano. Cierra Outlook y mata procesos OUTLOOK.EXE desde el Administrador de tareas.

Detalle COM: $detail
"@
        }
    }
}

$resolvedOutput = Resolve-ProjectPath $OutputPath
$outputDirectory = Split-Path -Parent $resolvedOutput
if ($outputDirectory -and -not (Test-Path $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$outlook = Get-OutlookApplication
$namespace = $outlook.GetNamespace("MAPI")

if ($Mailbox) {
    $store = $namespace.Stores | Where-Object { $_.DisplayName -eq $Mailbox } | Select-Object -First 1
    if ($null -eq $store) {
        throw "No se encontro el mailbox '$Mailbox'. Abre Outlook y revisa el nombre exacto del buzon."
    }
    $rootFolder = if ($AllFolders) { $store.GetRootFolder() } else { $store.GetDefaultFolder(6) }
}
else {
    $rootFolder = if ($AllFolders) { $namespace.DefaultStore.GetRootFolder() } else { $namespace.GetDefaultFolder(6) }
}

$rows = New-Object System.Collections.Generic.List[object]
Export-UnreadFromFolder $rootFolder $rows

$rows |
    Sort-Object date -Descending |
    Export-Csv -Path $resolvedOutput -NoTypeInformation -Encoding UTF8

Write-Host "Exportados $($rows.Count) correo(s) no leidos a $resolvedOutput"
