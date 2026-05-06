Param(
  [string]$ReportsRoot = "reports",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
  }
}

function Move-File([string]$src, [string]$dstDir) {
  Ensure-Dir $dstDir
  $name = Split-Path -Leaf $src
  $dst = Join-Path $dstDir $name
  if ($src -ieq $dst) { return }

  if ($DryRun) {
    Write-Host "[DRYRUN] $src -> $dst"
    return
  }

  # Evita pisar: si existe, agrega sufijo incremental.
  if (Test-Path -LiteralPath $dst) {
    $base = [System.IO.Path]::GetFileNameWithoutExtension($name)
    $ext = [System.IO.Path]::GetExtension($name)
    $i = 2
    do {
      $dst = Join-Path $dstDir ("{0}__{1}{2}" -f $base, $i, $ext)
      $i++
    } while (Test-Path -LiteralPath $dst)
  }

  Move-Item -LiteralPath $src -Destination $dst
}

function Target-Dir([string]$fileName) {
  $lower = $fileName.ToLowerInvariant()

  if ($lower -in @("standardized_prices.csv","opportunities.json","report.md")) { return "$ReportsRoot\\procurement_agent\\latest" }
  if ($lower -like "chief_*") { return "$ReportsRoot\\procurement_agent\\chief" }
  if ($lower -like "andes_*") { return "$ReportsRoot\\andes" }
  if ($lower -like "paso_a_paso_*") { return "$ReportsRoot\\paso_a_paso" }

  if ($lower -like "arthrex_*") { return "$ReportsRoot\\vendors\\arthrex" }
  if ($lower -like "baxter_*") { return "$ReportsRoot\\vendors\\baxter" }

  if ($lower -like "sugammadex_*") { return "$ReportsRoot\\pharma\\sugammadex" }

  if ($lower -like "clinical_market_*" -or $lower -like "canasta_clinical_market*" -or $lower -like "*clinical_market*") {
    if ($lower -like "lab_chile_*") { return "$ReportsRoot\\clinical_market\\lab_chile" }
    return "$ReportsRoot\\clinical_market"
  }

  if ($lower -like "lab_chile_*") { return "$ReportsRoot\\clinical_market\\lab_chile" }

  if ($lower -like "correo_*" -or $lower -like "avance_abastecimiento_*" -or $lower -like "resumen_*") {
    return "$ReportsRoot\\communications"
  }

  if ($lower -like "plan_*") { return "$ReportsRoot\\plans" }
  if ($lower -like "estrategia_*" -or $lower -like "consolidado_*" -or $lower -like "analisis_*" -or $lower -like "dossier_*" -or $lower -like "onepager_*") {
    return "$ReportsRoot\\andes"
  }

  return "$ReportsRoot\\_misc"
}

if (-not (Test-Path -LiteralPath $ReportsRoot)) {
  Write-Host "No existe la carpeta: $ReportsRoot"
  exit 0
}

# No mover README de reports
$items = Get-ChildItem -LiteralPath $ReportsRoot -File -Force | Where-Object { $_.Name -ne "README.md" }
if (-not $items) {
  Write-Host "Sin archivos a organizar en $ReportsRoot"
  exit 0
}

foreach ($item in $items) {
  $target = Target-Dir $item.Name
  Move-File $item.FullName $target
}

Write-Host "OK. Reportes organizados en $ReportsRoot" + ($(if($DryRun){" (dry-run)"}else{""}))

