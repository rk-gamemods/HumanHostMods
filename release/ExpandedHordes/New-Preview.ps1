#Requires -Version 7.0
param([Parameter(Mandatory)][string]$Path)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$bitmap = [System.Drawing.Bitmap]::new(1024, 1024)
$canvas = [System.Drawing.Graphics]::FromImage($bitmap)
$resources = [System.Collections.Generic.List[System.IDisposable]]::new()
function Brush([string]$hex) {
    $item = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($hex))
    $resources.Add($item)
    return $item
}
function Font([single]$size, [System.Drawing.FontStyle]$style = 'Bold') {
    $item = [System.Drawing.Font]::new('Arial', $size, $style, 'Pixel')
    $resources.Add($item)
    return $item
}
try {
    $canvas.SmoothingMode = 'AntiAlias'
    $canvas.TextRenderingHint = 'AntiAliasGridFit'
    $canvas.Clear([System.Drawing.ColorTranslator]::FromHtml('#11191C'))
    $white = Brush '#F4F1E8'
    $muted = Brush '#B4BDBC'
    $red = Brush '#EB674D'
    $dusk = Brush '#6D382F'
    $shadow = Brush '#172326'
    $foreground = Brush '#243236'
    $canvas.FillRectangle($red, 64, 66, 62, 7)
    $canvas.DrawString('HUMAN HOST MOD', (Font 25), $muted, 64, 96)
    $canvas.DrawString('EXPANDED', (Font 119), $white, 55, 173)
    $canvas.DrawString('HORDES', (Font 162), $white, 52, 294)
    $canvas.DrawString('MORE PRESSURE. TOUGHER SURVIVORS.', (Font 25), $red, 66, 503)
    $canvas.DrawString('Your Horde Night. Your settings.', (Font 28 'Regular'), $muted, 66, 551)
    $canvas.FillEllipse($dusk, 657, 654, 262, 262)
    # Original geometric crowd illustration; no game or third-party assets.
    for ($row = 0; $row -lt 3; $row++) {
        $step = 64 + $row * 23
        $head = 12 + $row * 7
        for ($x = -20 + $row * 19; $x -lt 1080; $x += $step) {
            $y = 715 + $row * 80 + (($x * 7) % 29)
            $ink = if ($row -eq 1) { $foreground } else { $shadow }
            $canvas.FillEllipse($ink, $x, $y, $head * 2, $head * 2)
            $canvas.FillEllipse($ink, $x - $head, $y + $head * 2, $head * 4, $head * 5)
        }
    }
    $canvas.FillRectangle((Brush '#0B1113'), 0, 956, 1024, 68)
    $canvas.DrawString('rk-gamemods', (Font 21 'Regular'), $muted, 66, 975)
    $bitmap.Save([System.IO.Path]::GetFullPath($Path), [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    foreach ($item in $resources) { $item.Dispose() }
    $canvas.Dispose()
    $bitmap.Dispose()
}
