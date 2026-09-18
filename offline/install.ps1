<#
.SYNOPSIS
    Installs or updates the VMS Zabbix agent from the wheels lying next to this script.

.DESCRIPTION
    Copy this whole folder onto the server and run the script from an elevated
    PowerShell. It needs no parameters: the folder it lives in is the package source.

    When the agent is not on the machine yet, the script installs it with its
    dependencies, registers the service and starts it. When it is already there, only
    the package itself is replaced, so pywin32 and pythonservice.exe are left alone.
    Nothing is touched when the installed version is not older than the one in the
    folder.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ServiceName = 'ZabbixVms'
$PackageName = 'zabbixvms'
$ConfigFolder = 'C:\ProgramData\LogicElements\ZabbixVms'
$Folder = $PSScriptRoot

function Stop-WithError([string]$Message) {
    Write-Host ''
    Write-Host "CHYBA: $Message" -ForegroundColor Red
    exit 1
}

function Get-PythonOutput([string]$Python, [string]$Code) {
    $output = & $Python -c $Code
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Python skončil s chybou, zjišťování stavu se nepovedlo."
    }
    return (($output -join '').Trim())
}

function Get-InstalledVersion([string]$Python) {
    $code = "import importlib.metadata as m; " +
            "print(next(iter([d.version for d in m.distributions() " +
            "if (d.metadata['Name'] or '').lower() == '$PackageName']), ''))"
    return Get-PythonOutput $Python $code
}

function Start-Agent() {
    Write-Host 'Spouštím službu...'
    try {
        Start-Service -Name $ServiceName
        (Get-Service -Name $ServiceName).WaitForStatus('Running', (New-TimeSpan -Seconds 60))
    } catch {
        Stop-WithError ("Služba nenastartovala: " + $_.Exception.Message + " Podívejte se do " +
            "$ConfigFolder\zabbixvms.log a do Event Logu Windows.")
    }
}

# --- rights -------------------------------------------------------------------------

$identity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Stop-WithError ('Skript potřebuje práva správce. Otevřete PowerShell přes ' +
        '"Spustit jako správce" a spusťte ho znovu.')
}

# --- interpreter --------------------------------------------------------------------

$command = Get-Command python -ErrorAction SilentlyContinue
if (-not $command) {
    Stop-WithError 'V PATH není žádný python.exe. Nainstalujte Python pro celý stroj.'
}
$python = $command.Source
Write-Host "Python:  $python"

if ($python.StartsWith($env:LOCALAPPDATA, [StringComparison]::OrdinalIgnoreCase)) {
    Write-Host ('VAROVÁNÍ: tenhle Python je nainstalovaný jen pro přihlášeného uživatele. ' +
        'Služba běží pod účtem LocalSystem a takovou instalaci nenajde.') -ForegroundColor Yellow
}

# --- packages in the folder ---------------------------------------------------------

$wheels = @(Get-ChildItem -Path $Folder -Filter '*.whl')
if ($wheels.Count -eq 0) {
    Stop-WithError "Ve složce $Folder nejsou žádné soubory .whl."
}

$tag = Get-PythonOutput $python "import sysconfig; print('cp' + sysconfig.get_config_var('py_version_nodot'))"

# A wheel built for another Python cannot be installed, so every package that ships one
# has to offer the tag of this interpreter; packages with no tag at all fit any Python.
$tagsOfPackage = @{}
$available = $null
foreach ($wheel in $wheels) {
    if ($wheel.Name -match '^([^-]+)-.*-(cp\d+)-') {
        $name = $Matches[1]
        if (-not $tagsOfPackage.ContainsKey($name)) { $tagsOfPackage[$name] = @() }
        $tagsOfPackage[$name] += $Matches[2]
    }
    if ($wheel.Name -match "^$PackageName-([0-9]+(\.[0-9]+)*)-") {
        $candidate = [version]$Matches[1]
        if (($null -eq $available) -or ($candidate -gt $available)) { $available = $candidate }
    }
}

$mismatched = @()
foreach ($name in $tagsOfPackage.Keys) {
    if ($tagsOfPackage[$name] -notcontains $tag) { $mismatched += $name }
}
if ($mismatched.Count -gt 0) {
    Stop-WithError ("Ve složce jsou balíčky " + (($mismatched | Sort-Object) -join ', ') +
        " jen pro jinou verzi Pythonu, tenhle je $tag. Stáhněte je znovu pro správnou verzi.")
}
if ($null -eq $available) {
    Stop-WithError "Ve složce $Folder není žádný wheel balíčku $PackageName."
}

# --- what is on the machine ---------------------------------------------------------

$installedText = Get-InstalledVersion $python
$installed = $null
if ($installedText) { $installed = [version]$installedText }
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

if ($installed) {
    Write-Host "Balíček: ve složce $available, na stroji $installed"
} else {
    Write-Host "Balíček: ve složce $available, na stroji zatím není"
}
if ($service) {
    Write-Host "Služba:  zaregistrovaná, stav $($service.Status)"
} else {
    Write-Host 'Služba:  zatím není zaregistrovaná'
}
Write-Host ''

# --- nothing to do ------------------------------------------------------------------

if ($installed -and ($installed -ge $available) -and $service) {
    Write-Host "Verze $installed není starší než $available, balíček zůstává beze změny."
    if ($service.Status -ne 'Running') {
        Start-Agent
    } else {
        Write-Host 'Služba běží, není co dělat.'
    }
    exit 0
}

# --- replace the package ------------------------------------------------------------

if ($service -and ($service.Status -ne 'Stopped')) {
    Write-Host 'Zastavuji službu...'
    Stop-Service -Name $ServiceName
    (Get-Service -Name $ServiceName).WaitForStatus('Stopped', (New-TimeSpan -Seconds 60))
}

if ($installed) {
    Write-Host "Aktualizuji balíček z $installed na $available..."
    & $python -m pip install --no-index --find-links $Folder --upgrade --no-deps $PackageName
} else {
    Write-Host "Instaluji balíček $available i s jeho závislostmi..."
    & $python -m pip install --no-index --find-links $Folder $PackageName
}
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'pip skončil s chybou, služba zůstala zastavená.'
}

# --- register the service when it is not there yet -----------------------------------

$fresh = $false
if (-not $service) {
    $scripts = Get-PythonOutput $python "import sysconfig; print(sysconfig.get_path('scripts'))"
    $agent = Join-Path $scripts 'zabbixvms-service.exe'
    if (-not (Test-Path $agent)) {
        Stop-WithError "Příkaz $agent po instalaci neexistuje."
    }
    Write-Host 'Registruji službu...'
    & $agent install
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError 'Registrace služby selhala.'
    }
    $fresh = $true
}

Start-Agent

# --- report -------------------------------------------------------------------------

Write-Host ''
$now = Get-InstalledVersion $python
$state = (Get-Service -Name $ServiceName).Status
Write-Host "Hotovo. Nainstalovaná verze $now, služba $state." -ForegroundColor Green
if ($fresh) {
    Write-Host ''
    Write-Host ("První instalace: upravte $ConfigFolder\config.json podle téhle turbíny " +
        "(adresa Zabbix serveru, název hosta, tabulky bufferů) a pak službu restartujte " +
        "příkazem: Restart-Service $ServiceName")
}
