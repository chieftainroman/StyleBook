param(
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$Family,
    [Parameter(Mandatory = $true)][double]$Size,
    [int]$Weight = 400
)

Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$culture = [System.Globalization.CultureInfo]::InvariantCulture
$fontWeight = [System.Windows.FontWeight]::FromOpenTypeWeight($Weight)
$typeface = New-Object System.Windows.Media.Typeface(
    (New-Object System.Windows.Media.FontFamily($Family)),
    [System.Windows.FontStyles]::Normal,
    $fontWeight,
    [System.Windows.FontStretches]::Normal
)
$formatted = New-Object System.Windows.Media.FormattedText(
    $Text,
    $culture,
    [System.Windows.FlowDirection]::LeftToRight,
    $typeface,
    $Size,
    [System.Windows.Media.Brushes]::Black,
    1.0
)

$geometry = $formatted.BuildGeometry((New-Object System.Windows.Point(0, 0))).GetFlattenedPathGeometry(0.2, [System.Windows.Media.ToleranceType]::Absolute)
$pathData = $geometry.ToString($culture) -replace '^F[01]', ''

[ordered]@{
    d = $pathData
    width = [Math]::Round($formatted.WidthIncludingTrailingWhitespace, 4)
    height = [Math]::Round($formatted.Height, 4)
    baseline = [Math]::Round($formatted.Baseline, 4)
} | ConvertTo-Json -Compress
