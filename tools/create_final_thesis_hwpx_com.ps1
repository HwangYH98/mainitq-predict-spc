param(
    [string]$MarkdownPath = "outputs\final_thesis_manuscript_29p.md",
    [string]$OutputPath = "outputs\final_thesis_manuscript_29p.hwpx"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$md = if ([IO.Path]::IsPathRooted($MarkdownPath)) { $MarkdownPath } else { Join-Path $root $MarkdownPath }
$out = if ([IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $root $OutputPath }
$log = Join-Path (Join-Path $root "outputs") "final_thesis_hwpx_com_build_log.txt"

if (-not (Test-Path -LiteralPath $md)) {
    throw "Markdown source was not found: $md"
}

$text = Get-Content -LiteralPath $md -Raw -Encoding UTF8
$blocks = [regex]::Split($text, '<!-- page \d+ -->') |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and ($_ -notmatch '^# MaintiQ Predict') }

if ($blocks.Count -ne 29) {
    throw "Expected 29 page blocks in markdown, found $($blocks.Count)"
}

function Convert-BlockText {
    param([string]$Block)
    $value = $Block
    $value = $value -replace '(?m)^##\s*', ''
    $value = $value -replace '(?m)^#\s*', ''
    $value = $value -replace '(?m)^\|[-:\s|]+\|?\s*$', ''
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($line in ($value -split "`r?`n")) {
        $trim = $line.Trim()
        if (-not $trim) {
            $lines.Add("")
            continue
        }
        if ($trim.StartsWith("|") -and $trim.EndsWith("|")) {
            $cells = $trim.Trim("|").Split("|") | ForEach-Object { $_.Trim() }
            $lines.Add(($cells -join "    |    "))
        } else {
            $lines.Add($trim)
        }
    }
    return (($lines -join "`r`n").Trim() + "`r`n")
}

function Insert-HwpText {
    param($Hwp, [string]$Text)
    $Hwp.HAction.GetDefault("InsertText", $Hwp.HParameterSet.HInsertText.HSet) | Out-Null
    $Hwp.HParameterSet.HInsertText.Text = $Text
    $ok = $Hwp.HAction.Execute("InsertText", $Hwp.HParameterSet.HInsertText.HSet)
    if (-not $ok) {
        throw "HWP InsertText failed."
    }
}

$messages = New-Object System.Collections.Generic.List[string]
$messages.Add("markdown=$md")
$messages.Add("output=$out")
$messages.Add("page_blocks=$($blocks.Count)")

Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue
$hwp = $null
try {
    $hwp = New-Object -ComObject HWPFrame.HwpObject
    $messages.Add("COM object created: HWPFrame.HwpObject")
    try { $hwp.XHwpWindows.Item(0).Visible = $false } catch {}

    for ($i = 0; $i -lt $blocks.Count; $i++) {
        Insert-HwpText -Hwp $hwp -Text (Convert-BlockText $blocks[$i])
        if ($i -lt $blocks.Count - 1) {
            $hwp.Run("BreakPage") | Out-Null
        }
    }

    $saved = [bool]$hwp.SaveAs($out, "HWPX", "")
    $messages.Add("SaveAs result=$saved")
    if (-not (Test-Path -LiteralPath $out)) {
        throw "HWPX save failed: $out"
    }
    $messages.Add("size_before_style_patch=$((Get-Item -LiteralPath $out).Length)")
} finally {
    if ($hwp -ne $null) {
        try { $hwp.Quit() | Out-Null } catch {}
    }
}

# Patch only stable document-wide style values: paper margins, 11pt text, and
# 200% line spacing.  The body XML remains Hancom-generated, avoiding the
# Korean rendering problem caused by hand-built paragraphs.
$patchScript = @'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import re, shutil, sys

path = Path(sys.argv[1])
tmp = path.with_suffix(".stylepatch.hwpx")
with ZipFile(path, "r") as src, ZipFile(tmp, "w", ZIP_DEFLATED) as dst:
    for item in src.infolist():
        data = src.read(item.filename)
        if item.filename == "Contents/header.xml":
            text = data.decode("utf-8")
            text = re.sub(r'height="1000"', 'height="1100"', text)
            text = re.sub(r'<hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/>',
                          '<hh:lineSpacing type="PERCENT" value="200" unit="HWPUNIT"/>', text)
            data = text.encode("utf-8")
        elif item.filename == "Contents/section0.xml":
            text = data.decode("utf-8")
            text = re.sub(r'<hp:margin header="[^"]*" footer="[^"]*" gutter="[^"]*" left="[^"]*" right="[^"]*" top="[^"]*" bottom="[^"]*"/>',
                          '<hp:margin header="0" footer="4252" gutter="0" left="9921" right="8504" top="9921" bottom="7087"/>',
                          text, count=1)
            data = text.encode("utf-8")
        dst.writestr(item, data)
shutil.move(str(tmp), str(path))
'@

$tmpPy = Join-Path (Join-Path $root "outputs") "_patch_hwpx_style.py"
$patchScript | Set-Content -LiteralPath $tmpPy -Encoding UTF8
try {
    & .\.venv\Scripts\python.exe $tmpPy $out
    $messages.Add("style_patch=ok")
    $messages.Add("size_after_style_patch=$((Get-Item -LiteralPath $out).Length)")
} finally {
    Remove-Item -LiteralPath $tmpPy -ErrorAction SilentlyContinue
}

$messages | Set-Content -LiteralPath $log -Encoding UTF8
Write-Output ($messages -join "`n")
