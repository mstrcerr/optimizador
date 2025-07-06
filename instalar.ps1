# Configuración
$pythonVersion = "3.11.9"
$ollamaVersion = "0.1.37"
$modeloIA = "phi3:mini"

# Verificar administrador
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# Configurar política de ejecución
Set-ExecutionPolicy Bypass -Scope Process -Force -ErrorAction SilentlyContinue

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
        Start-Sleep -Seconds 5  # Esperar instalación
    }
    
    Write-Host "[*] Instalando Python $pythonVersion..."
    winget install -e --id Python.Python.${pythonVersion.Replace('.','')} --silent --accept-package-agreements
    
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $host.UI.RawUI.ForegroundColor = "Green"
        Write-Host "[✓] Python instalado correctamente"
    } else {
        $host.UI.RawUI.ForegroundColor = "Red"
        Write-Host "[✗] Error: Falló la instalación de Python"
        exit
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
    
    # Descargar instalador
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $installerPath
    
    Write-Host "[*] Instalando Ollama..."
    Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait
    Start-Sleep -Seconds 10  # Esperar instalación
    
    # Verificar instalación
    if (Test-Path "C:\Program Files\Ollama\ollama.exe") {
        $host.UI.RawUI.ForegroundColor = "Green"
        Write-Host "[✓] Ollama instalado correctamente"
        Remove-Item $installerPath -Force
    } else {
        $host.UI.RawUI.ForegroundColor = "Red"
        Write-Host "[✗] Error: Falló la instalación de Ollama"
        exit
    }
}

# 3. Descargar modelo de IA
function Download-Model {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Descargando modelo de IA ($modeloIA)..."
    
    # Verificar si Ollama está en el PATH
    $env:Path += ";C:\Program Files\Ollama"
    
    Start-Process "ollama" -ArgumentList "pull $modeloIA" -WindowStyle Hidden -Wait
    
    $host.UI.RawUI.ForegroundColor = "Green"
    Write-Host "[✓] Modelo descargado (o ya existente)"
}

# 4. Instalar dependencias de Python
function Install-Dependencies {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Instalando dependencias de Python..."
    
    # Asegurar que pip está actualizado
    python -m pip install --upgrade pip
    
    # Instalar paquetes requeridos
    pip install requests psutil
    
    $host.UI.RawUI.ForegroundColor = "Green"
    Write-Host "[✓] Dependencias instaladas correctamente"
}

# 5. Crear acceso directo
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

# 6. Iniciar servicios
function Start-Services {
    $host.UI.RawUI.ForegroundColor = "Yellow"
    Write-Host "[*] Iniciando servicios en segundo plano..."
    
    # Detener Ollama si ya está corriendo
    Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
    
    # Iniciar Ollama en segundo plano
    Start-Process -FilePath "C:\Program Files\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
    
    $host.UI.RawUI.ForegroundColor = "Green"
    Write-Host "[✓] Servicios iniciados correctamente"
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

# 5. Crear acceso directo
Create-Shortcut

# 6. Iniciar servicios
Start-Services

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
Write-Host "- El acceso directo ejecutará automáticamente el programa"
Write-Host ""
$host.UI.RawUI.ForegroundColor = "White"

# Iniciar el optimizador automáticamente
$choice = Read-Host "¿Deseas ejecutar el optimizador ahora? (s/n)"
if ($choice -eq 's' -or $choice -eq 'S') {
    $scriptPath = Join-Path -Path $pwd -ChildPath "optimizador.py"
    Start-Process python -ArgumentList "`"$scriptPath`""
}