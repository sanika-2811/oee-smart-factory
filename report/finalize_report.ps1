# Updates all fields (TOC page numbers) with Microsoft Word, saves the .docx and exports a PDF.
#   powershell -ExecutionPolicy Bypass -File reportinalize_report.ps1
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$name = "OEE_Smart_Factory_Project_Report"
$work = Join-Path $env:TEMP "oee_report_work"            # work outside OneDrive to avoid sync locks
New-Item -ItemType Directory -Force $work | Out-Null
Copy-Item (Join-Path $dir "$name.docx") (Join-Path $work "$name.docx") -Force
$docx = Join-Path $work "$name.docx"
$pdf = Join-Path $work "$name.pdf"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    Write-Host "opening ..."
    $doc = $word.Documents.Open($docx, $false, $false, $false)
    Write-Host "opened; updating fields ..."
    $doc.Fields.Update() | Out-Null
    $pages = $doc.ComputeStatistics(2)
    Write-Host "pages (total, incl. front matter): $pages"
    $doc.Fields.Update() | Out-Null
    $doc.Save()
    Write-Host "exporting PDF ..."
    $doc.ExportAsFixedFormat($pdf, 17)
    $doc.Close($false)
} finally {
    $word.Quit()
}
Copy-Item $docx (Join-Path $dir "$name.docx") -Force
Copy-Item $pdf (Join-Path $dir "$name.pdf") -Force
Write-Host "done"
