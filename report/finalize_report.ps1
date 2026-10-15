# Updates all fields (TOC page numbers) with Microsoft Word, saves the .docx and exports a PDF.
#   powershell -ExecutionPolicy Bypass -File report\finalize_report.ps1
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
    $doc = $word.Documents.Open($docx, $false, $false, $false)
    $doc.Fields.Update() | Out-Null
    $pages = $doc.ComputeStatistics(2)
    $doc.Fields.Update() | Out-Null
    $doc.Save()
    Copy-Item $docx (Join-Path $dir "$name.docx") -Force          # keep the field-updated docx even if PDF export stalls
    Write-Host "pages (total, incl. front matter): $pages ; docx saved"
    $doc.SaveAs2($pdf, 17)
    $doc.Close($false)
} finally {
    $word.Quit()
}
Copy-Item $pdf (Join-Path $dir "$name.pdf") -Force
Write-Host "done"
