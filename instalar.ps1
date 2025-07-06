# Instalador Automático para Optimizador Windows con IA
# Repositorio: https://github.com/mstrcerr/optimizador
# Debe ejecutarse como administrador

# Configuración
$pythonVersion = "3.11.9"
$ollamaVersion = "0.1.37"
$modeloIA = "phi3:mini"
$scriptUrl = "https://raw.githubusercontent.com/mstrcerr/optimizador/main/optimizador.py"

# Verificar administrador
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# Configurar política de ejecución
Set-ExecutionPolicy Bypass -Scope Process -Force -ErrorAction SilentlyContinue

# Configurar manejo de errores
$ErrorActionPreference = 'Stop'
trap {
    $host.UI.RawUI.ForegroundColor = "Red"
    Write-Host "`n[!] ERROR: $($_.Exception.Message)" 
    Write-Host "En línea: $($_.InvocationInfo.ScriptLineNumber)" -ForegroundColor Yellow
    $host.UI.RawUI.ForegroundColor = "White"
    exit 1
}

# Configurar colores
$host.UI.RawUI.ForegroundColor = "Green"
Write-Host "================================================================"
Write-Host "         INSTALADOR AUTOMÁTICO PARA OPTIMIZADOR WINDOWS         "
Write-Host "================================================================"
$host.UI.RawUI.ForegroundColor = "White"

# 1. Instalar Python si no existe
function Install-Python {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Verificando instalación de Python..."
    
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $host.UI.RawUI.ForegroundColor = "Green"
        Write-Host "[✓] Python ya está instalado"
        return
    }
    
    # Instalar Winget si no existe
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "[*] Instalando Winget..."
        $wingetUrl = "https://aka.ms/getwinget"
        $wingetPath = "$env:TEMP\Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle"
        Invoke-WebRequest -Uri $wingetUrl -OutFile $wingetPath
        Add-AppxPackage -Path $wingetPath
        Start-Sleep -Seconds 5
    }
    
    Write-Host "[*] Instalando Python $pythonVersion..."
    winget install -e --id Python.Python.3119 --silent --accept-package-agreements
    
    # Actualizar PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $host.UI.RawUI.ForegroundColor = "Green"
        Write-Host "[✓] Python instalado correctamente"
    } else {
        throw "Falló la instalación de Python"
    }
}

# 2. Instalar Ollama
function Install-Ollama {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Verificando instalación de Ollama..."
    
    if (Test-Path "C:\Program Files\Ollama\ollama.exe") {
        $host.UI.RawUI.ForegroundColor = "Green"
        Write-Host "[✓] Ollama ya está instalado"
        return
    }
    
    Write-Host "[*] Descargando Ollama..."
    $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
    $installerPath = "$env:TEMP\OllamaSetup.exe"
    
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $installerPath
    
    Write-Host "[*] Instalando Ollama (esto puede tomar un momento)..."
    Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait
    Start-Sleep -Seconds 15
    
    # Verificar instalación
    if (Test-Path "C:\Program Files\Ollama\ollama.exe") {
        $host.UI.RawUI.ForegroundColor = "Green"
        Write-Host "[✓] Ollama instalado correctamente"
        Remove-Item $installerPath -Force
    } else {
        throw "Falló la instalación de Ollama"
    }
}

# 3. Descargar modelo de IA
function Download-Model {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Descargando modelo de IA ($modeloIA)..."
    
    # Añadir Ollama al PATH
    $env:Path += ";C:\Program Files\Ollama"
    
    # Iniciar servicio Ollama
    Start-Process -FilePath "C:\Program Files\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
    
    # Descargar modelo
    Start-Process "ollama" -ArgumentList "pull $modeloIA" -WindowStyle Hidden -Wait
    
    $host.UI.RawUI.ForegroundColor = "Green"
    Write-Host "[✓] Modelo descargado correctamente"
}

# 4. Instalar dependencias de Python
function Install-Dependencies {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Instalando dependencias de Python..."
    
    python -m pip install --upgrade pip
    pip install requests psutil pywin32
    
    $host.UI.RawUI.ForegroundColor = "Green"
    Write-Host "[✓] Dependencias instaladas correctamente"
}

# 5. Descargar script optimizador
function Download-Script {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Descargando script optimizador..."
    
    $scriptPath = Join-Path -Path $pwd -ChildPath "optimizador.py"
    Invoke-WebRequest -Uri $scriptUrl -OutFile $scriptPath
    
    if (Test-Path $scriptPath) {
        $host.UI.RawUI.ForegroundColor = "Green"
        Write-Host "[✓] Script descargado correctamente"
    } else {
        throw "No se pudo descargar el script"
    }
}

# 6. Crear acceso directo
function Create-Shortcut {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Creando acceso directo..."
    
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path -Path $desktopPath -ChildPath "Optimizador.lnk"
    $scriptPath = Join-Path -Path $pwd -ChildPath "optimizador.py"
    
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = "python"
    $Shortcut.Arguments = "`"$scriptPath`""
    $Shortcut.WorkingDirectory = $pwd
    $Shortcut.IconLocation = "C:\Windows\System32\cmd.exe, 0"
    $Shortcut.Save()
    
    $host.UI.RawUI.ForegroundColor = "Green"
    Write-Host "[✓] Acceso directo creado en el escritorio"
}

# --- Flujo principal de instalación ---
Write-Host "Iniciando instalación..." -ForegroundColor Cyan

# 1. Instalar Python
Install-Python

# 2. Instalar Ollama
Install-Ollama

# 3. Descargar modelo de IA
Download-Model

# 4. Instalar dependencias de Python
Install-Dependencies

# 5. Descargar script optimizador
Download-Script

# 6. Crear acceso directo
Create-Shortcut

# Mensaje final
$host.UI.RawUI.ForegroundColor = "Green"
Write-Host "================================================================"
Write-Host "         INSTALACIÓN COMPLETADA EXITOSAMENTE!"
Write-Host "================================================================"
$host.UI.RawUI.ForegroundColor = "Cyan"
Write-Host "Para ejecutar el optimizador:"
Write-Host "1. Busca el acceso directo 'Optimizador' en tu escritorio"
Write-Host "2. Haz doble clic para ejecutarlo"
Write-Host ""
Write-Host "Notas importantes:"
Write-Host "- La primera ejecución puede tardar 1-2 minutos mientras carga el modelo"
Write-Host "- Debes aceptar el aviso de seguridad para ejecutar como administrador"
Write-Host ""
$host.UI.RawUI.ForegroundColor = "White"

# Iniciar el optimizador automáticamente
$choice = Read-Host "¿Deseas ejecutar el optimizador ahora? (s/n)"
if ($choice -eq 's' -or $choice -eq 'S') {
    $scriptPath = Join-Path -Path $pwd -ChildPath "optimizador.py"
    Start-Process python -ArgumentList "`"$scriptPath`""
}