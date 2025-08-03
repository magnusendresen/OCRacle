param(
  [int]$X = 100,
  [int]$Y = 100,
  [int]$W = 80,   # i tegnkolonner, eller velg en passende konvertering
  [int]$H = 25    # i tegnrader
)

# Hent konsoll-HWND
$ps = Get-Process -Id $PID
Start-Sleep -Milliseconds 20
$hwnd = $ps.MainWindowHandle

# Definer MoveWindow
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class PInvoke {
  [DllImport("user32.dll")]
  public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
}
"@

# Flytt vinduet (her fortsatt i tegn-enheter; for piksler må du oversette)
[PInvoke]::MoveWindow($hwnd, $X, $Y, $W * 8, $H * 16, $true)

# Kjør Python og pause
python main.py
pause
