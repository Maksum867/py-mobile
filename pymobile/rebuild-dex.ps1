<#
.SYNOPSIS
    Rebuild the prebuilt classes.dex from the Java sources.

.DESCRIPTION
    The APK ships a precompiled classes.dex holding the launcher activity and
    the view renderer. Editing anything under pymobile/resources/android/java/
    has no effect on a device until that dex is rebuilt — the APK still builds
    cleanly, so the symptom is simply "my new widget does not render".

    Run this after touching any .java file in the framework.

.EXAMPLE
    .\rebuild-dex.ps1

.EXAMPLE
    .\rebuild-dex.ps1 -Verify
    Rebuild, then check that the expected symbols are present.
#>

[CmdletBinding()]
param(
    # Where the Android SDK lives. Empty means "work it out below".
    [string] $SdkHome,

    # Confirm the rebuilt dex contains the renderer symbols.
    [switch] $Verify
)

$ErrorActionPreference = 'Stop'

function Find-One {
    param([string] $Pattern, [switch] $Directory)

    return @(Get-ChildItem $Pattern -ErrorAction SilentlyContinue |
             Where-Object { -not $Directory -or $_.PSIsContainer } |
             Sort-Object Name -Descending)
}

# --- locate the SDK -------------------------------------------------------
# An SDK can come from `pymobile setup-sdk` (~/.andro) or from Android Studio,
# which installs somewhere else entirely. Checking one location only turns a
# working machine into "not found", so every usual place is tried and the
# error lists all of them.
$sdkCandidates = @()
if ($SdkHome)                  { $sdkCandidates += $SdkHome }
if ($env:PYMOBILE_SDK_HOME)    { $sdkCandidates += $env:PYMOBILE_SDK_HOME }
if ($env:ANDROID_HOME)         { $sdkCandidates += $env:ANDROID_HOME }
if ($env:ANDROID_SDK_ROOT)     { $sdkCandidates += $env:ANDROID_SDK_ROOT }
$sdkCandidates += (Join-Path $HOME '.andro')
if ($env:LOCALAPPDATA)         { $sdkCandidates += (Join-Path $env:LOCALAPPDATA 'Android\Sdk') }
$sdkCandidates += (Join-Path $HOME 'AppData\Local\Android\Sdk')
$sdkCandidates += (Join-Path $HOME 'Library\Android\sdk')
$sdkCandidates += (Join-Path $HOME 'Android\Sdk')

$sdk = $null
foreach ($candidate in ($sdkCandidates | Select-Object -Unique)) {
    if (-not (Test-Path $candidate)) { continue }
    # A usable SDK needs both, and build-tools must not be an empty directory.
    $hasTools = (Find-One (Join-Path $candidate 'build-tools\*') -Directory).Count -gt 0
    $hasJar   = (Find-One (Join-Path $candidate 'platforms\*\android.jar')).Count -gt 0
    if ($hasTools -and $hasJar) { $sdk = $candidate; break }
}

if (-not $sdk) {
    Write-Host "No usable Android SDK found. Looked in:" -ForegroundColor Red
    foreach ($candidate in ($sdkCandidates | Select-Object -Unique)) {
        $state = if (-not (Test-Path $candidate)) {
            'missing'
        } elseif ((Find-One (Join-Path $candidate 'build-tools\*') -Directory).Count -eq 0) {
            'no build-tools'
        } else {
            'no platforms/*/android.jar'
        }
        Write-Host ("  {0,-26} {1}" -f $state, $candidate)
    }
    Write-Host "`nFix it with either:" -ForegroundColor Yellow
    Write-Host "  pymobile setup-sdk                       # downloads ~800 MB"
    Write-Host "  .\rebuild-dex.ps1 -SdkHome 'D:\path\to\sdk'"
    throw "Android SDK not found."
}

Write-Host "Using the SDK in $sdk" -ForegroundColor Cyan

$buildTools = (Find-One (Join-Path $sdk 'build-tools\*') -Directory)[0].FullName
$androidJar = (Find-One (Join-Path $sdk 'platforms\*\android.jar'))[0].FullName

# --- locate a JDK ---------------------------------------------------------
# The JDK is independent of the SDK: setup-sdk unpacks one as jdk-17.0.13+11
# (note the '+', which is why paths stay quoted), Android Studio ships its own
# as jbr, and a system install answers on PATH.
$jdk = $null
if ($env:JAVA_HOME -and (Find-One (Join-Path $env:JAVA_HOME 'bin\javac*')).Count -gt 0) {
    $jdk = $env:JAVA_HOME
}
if (-not $jdk) {
    foreach ($pattern in @((Join-Path $sdk 'jdk-17*'),
                           (Join-Path $HOME '.andro\jdk-17*'),
                           (Join-Path $sdk '..\jbr'),
                           (Join-Path $HOME 'AppData\Local\Programs\Android Studio\jbr'))) {
        $hit = Find-One $pattern -Directory
        if ($hit.Count -gt 0 -and
            (Find-One (Join-Path $hit[0].FullName 'bin\javac*')).Count -gt 0) {
            $jdk = $hit[0].FullName
            break
        }
    }
}
if (-not $jdk) {
    $onPath = Get-Command javac -ErrorAction SilentlyContinue
    if ($onPath) { $jdk = Split-Path (Split-Path $onPath.Source -Parent) -Parent }
}
if (-not $jdk) {
    throw "No JDK found. Set JAVA_HOME, or run 'pymobile setup-sdk' to download one."
}

# Windows ships javac.exe/jar.exe and wraps d8 in a .bat; other platforms use
# bare names. Checking both keeps the script usable from PowerShell Core on
# macOS and Linux, and lets it be tested there.
function Resolve-Tool {
    param([string] $Directory, [string[]] $Names, [string] $What)

    foreach ($name in $Names) {
        $candidate = Join-Path $Directory $name
        if (Test-Path $candidate) { return $candidate }
    }
    throw "Missing tool: $What (looked for $($Names -join ', ') in $Directory)"
}

$jdkBin = Join-Path $jdk 'bin'
$javac  = Resolve-Tool $jdkBin     @('javac.exe', 'javac') 'javac'
$jar    = Resolve-Tool $jdkBin     @('jar.exe', 'jar')     'jar'
$d8     = Resolve-Tool $buildTools @('d8.bat', 'd8')       'd8'

Write-Host "  JDK         $jdk"
Write-Host "  build-tools $buildTools"
Write-Host "  android.jar $androidJar"

# --- locate the project ---------------------------------------------------
# Paths are resolved against the script's own location, not the working
# directory, so the script works from anywhere — including a copy that was
# moved one directory deeper.
$root      = $PSScriptRoot
$javaDir   = Join-Path $root 'pymobile\resources\android\java'
$targetDex = Join-Path $root 'pymobile\resources\android\prebuilt\arm64-v8a\classes.dex'

if (-not (Test-Path $javaDir)) {
    # A copy inside pymobile\ is the usual mistake; find the real root.
    $parent = Split-Path $root -Parent
    if ($parent -and (Test-Path (Join-Path $parent 'pymobile\resources\android\java'))) {
        $root      = $parent
        $javaDir   = Join-Path $root 'pymobile\resources\android\java'
        $targetDex = Join-Path $root 'pymobile\resources\android\prebuilt\arm64-v8a\classes.dex'
        Write-Host "Note: using the repository root at $root" -ForegroundColor Yellow
    } else {
        Write-Host "This script must sit in the repository root." -ForegroundColor Red
        Write-Host "  expected: <repo>\rebuild-dex.ps1  (next to pyproject.toml)"
        Write-Host "  found at: $root"
        throw "$javaDir does not exist."
    }
}

$sources = @(Get-ChildItem (Join-Path $javaDir '*.java') | ForEach-Object { $_.FullName })
if ($sources.Count -eq 0) { throw "No .java sources in $javaDir" }
Write-Host "  sources     $($sources.Count) files" -ForegroundColor Cyan

# --- build ----------------------------------------------------------------
# GetTempPath() works everywhere; $env:TEMP is Windows-only.
$work = Join-Path ([System.IO.Path]::GetTempPath()) 'pymobile-dexbuild'
Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
$null = New-Item -ItemType Directory -Force -Path (Join-Path $work 'classes'),
                                                  (Join-Path $work 'dex')

# 1. compile. -source/-target 8 because d8 rejects newer bytecode; UTF-8
#    because the sources carry non-ASCII strings and javac would otherwise
#    fall back to the console codepage.
Write-Host "`n[1/4] javac" -ForegroundColor Yellow
& $javac -source 8 -target 8 -encoding UTF-8 -nowarn `
    -bootclasspath $androidJar -classpath $androidJar `
    -d (Join-Path $work 'classes') $sources
if ($LASTEXITCODE -ne 0) { throw "javac failed with exit code $LASTEXITCODE" }

# 2. one jar rather than a list of .class files: it keeps the command line
#    short (Windows caps it near 32k) and lets d8 resolve inner classes.
Write-Host "[2/4] jar" -ForegroundColor Yellow
& $jar cf (Join-Path $work 'classes.jar') -C (Join-Path $work 'classes') .
if ($LASTEXITCODE -ne 0) { throw "jar failed with exit code $LASTEXITCODE" }

Write-Host "[3/4] d8" -ForegroundColor Yellow
& $d8 --min-api 21 --lib $androidJar `
    --output (Join-Path $work 'dex') (Join-Path $work 'classes.jar')
if ($LASTEXITCODE -ne 0) { throw "d8 failed with exit code $LASTEXITCODE" }

$freshDex = Join-Path $work 'dex\classes.dex'
if (-not (Test-Path $freshDex)) { throw "d8 produced no classes.dex" }

Write-Host "[4/4] install" -ForegroundColor Yellow
Copy-Item $freshDex $targetDex -Force

$size = (Get-Item $targetDex).Length
Write-Host "`nclasses.dex rebuilt: $size bytes" -ForegroundColor Green
Write-Host "  -> $targetDex"

# --- optional verification -----------------------------------------------
if ($Verify) {
    Write-Host "`nVerifying symbols" -ForegroundColor Cyan
    $bytes = [System.IO.File]::ReadAllBytes($targetDex)
    $text  = [System.Text.Encoding]::ASCII.GetString($bytes)
    $missing = @()
    foreach ($symbol in @('buildChild', 'buildGrid', 'buildSafeArea', 'buildFlex',
                          'buildDivider', 'childParams', 'applyMargin',
                          'applyConstraints', 'deviceLanguage')) {
        if ($text.Contains($symbol)) {
            Write-Host "  ok   $symbol" -ForegroundColor Green
        } else {
            Write-Host "  MISS $symbol" -ForegroundColor Red
            $missing += $symbol
        }
    }
    if ($missing.Count -gt 0) {
        throw "$($missing.Count) symbol(s) missing from the dex"
    }
    Write-Host "`nAll symbols present." -ForegroundColor Green
}

Write-Host "`nNext: pymobile build --native" -ForegroundColor Cyan
