import os
import shutil
import subprocess
import ctypes
import winreg
import psutil
import requests
import json
import platform
import time
import sys
import re
import logging
from datetime import datetime, timedelta
from functools import wraps

# --- CONFIGURACIÓN DE LOGGING --- #
logging.basicConfig(
    filename='optimizador.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE OLLAMA PHI3-MINI --- #
OLLAMA_URL = "http://localhost:11434/api/generate"  # Endpoint estable
MODEL_NAME = "phi3:mini"  # Modelo ultra ligero (2.2 GB)
SYSTEM_PROMPT = """
Eres un experto en optimización de sistemas Windows. Analiza los datos del sistema y recomienda acciones específicas.
Prioriza seguridad y estabilidad. Solo recomienda eliminar archivos si son claramente innecesarios.
Evita recomendar eliminar: pagefile.sys, hiberfil.sys, archivos del sistema.
Usa nombres de acciones compatibles: limpieza_temporales, vaciar_papelera, optimizar_arranque, limpiar_cache_navegadores, 
analizar_disco, ejecutar_cleanmgr, optimizar_servicios, configurar_alto_rendimiento, deshabilitar_efectos_visuales, 
desfragmentar_disco, optimizar_red, deshabilitar_telemetria, optimizar_rendimiento_visual.
Respuestas deben ser SOLO JSON sin texto adicional.
"""
OLLAMA_TIMEOUT = 300  # 5 minutos
MAX_RETRIES = 2  # Reintentos para conexiones fallidas

# --- CONFIGURACIÓN INICIAL --- #
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'

# --- DECORADOR PARA REINTENTOS --- #
def retry_on_error(max_retries=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    logger.error(f"Intento {retries}/{max_retries} fallido en {func.__name__}: {str(e)}")
                    if retries < max_retries:
                        time.sleep(delay)
                    else:
                        logger.error(f"Fallo definitivo en {func.__name__}: {str(e)}")
                        raise
        return wrapper
    return decorator

def es_admin():
    """Verifica si el script se ejecuta como administrador"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def solicitar_admin():
    """Solicita elevación de privilegios"""
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# --- VERIFICACIÓN DE MEMORIA --- #
def verificar_memoria_suficiente(min_gb=4):
    """Verifica si hay suficiente memoria RAM disponible"""
    mem = psutil.virtual_memory()
    disponible_gb = mem.available / (1024 ** 3)  # Convertir a GB
    return disponible_gb >= min_gb

def obtener_memoria_disponible():
    """Obtiene la memoria RAM disponible en GB"""
    mem = psutil.virtual_memory()
    return mem.available / (1024 ** 3)

def sugerir_liberar_memoria():
    """Sugiere acciones para liberar memoria RAM"""
    print(f"\n{Colors.YELLOW}Para liberar memoria RAM, puedes:{Colors.END}")
    print("1. Cerrar aplicaciones que consuman mucha memoria (navegadores, editores de video, juegos)")
    print("2. Reiniciar tu computadora antes de usar esta función")
    print("3. Usar la opción de limpieza básica (opción 1) antes de intentar la auto-optimización")
    print("4. Reducir la cantidad de programas que se inician automáticamente (opción 4)")

# --- FUNCIÓN PARA CONSULTAR A PHI3-MINI --- #
def consultar_phi3(prompt, sistema_info=None, max_tokens=1000, temperatura=0.7):
    """Consulta al modelo Phi3-mini con timeout extendido y reintentos"""
    if sistema_info is None:
        sistema_info = ""
    
    # Preparamos el prompt completo
    prompt_completo = f"[SYS]{SYSTEM_PROMPT}[/SYS]\n[INFO]{sistema_info}[/INFO]\n[USER]{prompt}"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt_completo,
        "stream": False,
        "options": {
            "temperature": temperatura,
            "num_predict": max_tokens
        }
    }
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Verificar primero si Ollama está disponible
            test_response = requests.get("http://localhost:11434", timeout=10)
            if test_response.status_code != 200:
                return None, "Ollama no está disponible (localhost:11434 no responde)"
            
            # Hacer la solicitud con timeout extendido
            response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            response.raise_for_status()
            
            # La respuesta completa es un objeto JSON (no streaming)
            json_response = response.json()
            return json_response.get("response", "").strip(), None
            
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                print(f"{Colors.YELLOW}Timeout. Reintentando ({attempt+1}/{MAX_RETRIES})...{Colors.END}")
                time.sleep(5)  # Esperar antes de reintentar
            else:
                return None, f"Timeout extendido ({OLLAMA_TIMEOUT}s) excedido"
        except requests.exceptions.ConnectionError:
            return None, "No se pudo conectar a Ollama. ¿Está ejecutándose?"
        except Exception as e:
            return None, f"Error al consultar a Phi3: {str(e)}"

# --- AUTO-OPTIMIZACIÓN CON PHI3-MINI --- #
def auto_optimizar_con_phi3():
    """Usa Phi3-mini para analizar el sistema y aplicar optimizaciones automáticas"""
    # 1. Verificar memoria suficiente
    memoria_disponible = obtener_memoria_disponible()
    print(f"{Colors.CYAN}\nMemoria RAM disponible: {memoria_disponible:.2f} GB{Colors.END}")
    
    if memoria_disponible < 3:
        print(f"{Colors.RED}Advertencia: Memoria RAM baja ({memoria_disponible:.2f} GB).{Colors.END}")
        print("Phi3-mini necesita al menos 3 GB de RAM libre para funcionar correctamente.")
        sugerir_liberar_memoria()
        
        confirmar = input("\n¿Deseas intentarlo de todos modos? (s/n): ").lower()
        if confirmar != 's':
            return
    
    # 2. Recopilar información del sistema (optimizada)
    sistema_info = generar_reporte_sistema()
    print(f"{Colors.CYAN}Recopilando información del sistema para Phi3-mini...{Colors.END}")
    logger.info("Recopilando información del sistema para Phi3-mini")
    
    # 3. Consultar a Phi3-mini para obtener plan de optimización
    prompt = (
        "Analiza el estado del sistema Windows y genera un plan de optimización JSON con acciones específicas. "
        "Considera: limpieza de archivos temporales, gestión de programas de inicio, análisis de disco. "
        "Formato de respuesta: {\"acciones\": [{\"tipo\": \"limpieza_temporales\", \"intensidad\": \"media\"}, ...]}"
        "Asegúrate de que la respuesta es SOLO el JSON, sin ningún texto adicional. "
        "Usa SOLO los nombres de acciones compatibles definidos en el SYSTEM_PROMPT."
    )
    
    print(f"{Colors.CYAN}Consultando a Phi3-mini para obtener plan de optimización...{Colors.END}")
    print(f"{Colors.YELLOW}Esta operación puede tardar 1-2 minutos...{Colors.END}")
    logger.info("Consultando a Phi3-mini para plan de optimización")
    respuesta, error = consultar_phi3(prompt, sistema_info)
    
    if error:
        print(f"{Colors.RED}Error: {error}{Colors.END}")
        logger.error(f"Error en consulta a Phi3-mini: {error}")
        print("Por favor, asegúrate de que Ollama está instalado y ejecutándose.")
        print("Puedes iniciarlo con el comando: ollama serve")
        return
    
    try:
        # Extraer JSON de la respuesta
        inicio_json = respuesta.find('{')
        fin_json = respuesta.rfind('}') + 1
        if inicio_json == -1 or fin_json == 0:
            raise ValueError("No se encontró JSON en la respuesta")
        json_str = respuesta[inicio_json:fin_json]
        plan = json.loads(json_str)
        
        print(f"{Colors.GREEN}\nPlan de optimización generado por Phi3-mini:{Colors.END}")
        logger.info(f"Plan de optimización recibido: {json.dumps(plan, indent=2)}")
        for i, accion in enumerate(plan.get('acciones', []), 1):
            print(f"{i}. {accion['tipo']} (intensidad: {accion.get('intensidad', 'media')}")
        
        # 4. Ejecutar acciones
        confirmacion = input("\n¿Ejecutar el plan de optimización? (s/n): ").lower()
        if confirmacion == 's':
            logger.info("Ejecutando plan de optimización")
            ejecutar_plan_optimizacion(plan)
            print(f"{Colors.GREEN}\n✓ Optimización completada usando recomendaciones de Phi3-mini{Colors.END}")
        else:
            print("Optimización cancelada")
            logger.info("Plan de optimización cancelado por el usuario")
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"{Colors.RED}Error al procesar respuesta de Phi3-mini: {str(e)}{Colors.END}")
        logger.error(f"Error procesando respuesta Phi3-mini: {str(e)} - Respuesta: {respuesta[:500]}")
        print(f"Respuesta completa:\n{respuesta[:500]}...")

# --- FUNCIONES DE LIMPIEZA MEJORADAS --- #
def limpiar_archivos_temporales(intensidad="media"):
    """Elimina archivos temporales con diferentes niveles de intensidad"""
    directorios = [
        os.environ.get('TEMP'),
        os.environ.get('TMP'),
        os.path.join(os.environ['SystemRoot'], 'Temp'),
        os.path.join(os.environ['SystemRoot'], 'Prefetch'),
        os.path.join(os.environ['LOCALAPPDATA'], 'Temp')
    ]
    
    # Directorios adicionales para alta intensidad
    if intensidad == "alta":
        directorios.extend([
            os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Microsoft', 'Windows', 'INetCache'),
            os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache'),
        ])
    
    espacio_liberado = 0
    dias_limite = 7 if intensidad == "baja" else 3 if intensidad == "media" else 1
    archivos_eliminados = []
    logger.info(f"Iniciando limpieza de temporales (intensidad={intensidad})")
    
    for directorio in directorios:
        if directorio and os.path.exists(directorio):
            print(f"\n{Colors.BLUE}Limpiando ({intensidad}): {directorio}{Colors.END}")
            try:
                for item in os.listdir(directorio):
                    ruta_completa = os.path.join(directorio, item)
                    try:
                        # Calcular antigüedad del archivo
                        tiempo_mod = datetime.fromtimestamp(os.path.getmtime(ruta_completa))
                        antiguedad = datetime.now() - tiempo_mod
                        
                        if antiguedad < timedelta(days=dias_limite):
                            continue
                            
                        if os.path.isfile(ruta_completa):
                            tamaño = os.path.getsize(ruta_completa)
                            os.remove(ruta_completa)
                            espacio_liberado += tamaño
                            archivos_eliminados.append(ruta_completa)
                        elif os.path.isdir(ruta_completa):
                            tamaño = obtener_tamaño_carpeta(ruta_completa)
                            shutil.rmtree(ruta_completa)
                            espacio_liberado += tamaño
                            archivos_eliminados.append(ruta_completa + " (carpeta)")
                    except PermissionError as pe:
                        logger.warning(f"Permiso denegado: {ruta_completa} - {str(pe)}")
                    except FileNotFoundError as fnfe:
                        logger.warning(f"Archivo no encontrado: {ruta_completa} - {str(fnfe)}")
                    except Exception as e:
                        logger.error(f"Error al eliminar {ruta_completa}: {str(e)}")
            except Exception as e:
                logger.error(f"Error al acceder al directorio {directorio}: {str(e)}")
    
    # Mostrar resumen detallado
    if archivos_eliminados:
        print(f"\n{Colors.CYAN}Archivos eliminados ({len(archivos_eliminados)}):{Colors.END}")
        for i, archivo in enumerate(archivos_eliminados[:5], 1):
            print(f"{i}. {archivo}")
        if len(archivos_eliminados) > 5:
            print(f"... y {len(archivos_eliminados) - 5} más")
        logger.info(f"Se eliminaron {len(archivos_eliminados)} archivos. Espacio liberado: {bytes_a_mb(espacio_liberado)} MB")
    else:
        logger.info("No se encontraron archivos para eliminar")
                
    return espacio_liberado

def vaciar_papelera():
    """Vacía la papelera de reciclaje"""
    try:
        # Verificar si la papelera está vacía
        SHERB_NOCONFIRMATION = 0x000001
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, SHERB_NOCONFIRMATION)
        if result == 0:
            logger.info("Papelera vaciada exitosamente")
            return True
        else:
            logger.warning("La papelera ya estaba vacía")
            return True
    except Exception as e:
        logger.error(f"Error al vaciar papelera: {str(e)}")
        return False

def limpiar_cache_navegadores(intensidad="media"):
    """Limpia caché de navegadores con intensidad variable"""
    navegadores = {
        'Edge': os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache'),
        'Firefox': os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'Profiles')
    }
    
    espacio_liberado = 0
    dias_limite = 30 if intensidad == "baja" else 14 if intensidad == "media" else 1
    archivos_eliminados = []
    logger.info(f"Iniciando limpieza de cache de navegadores (intensidad={intensidad})")
    
    for nombre, ruta_base in navegadores.items():
        if not os.path.exists(ruta_base):
            continue
            
        print(f"\n{Colors.BLUE}Limpiando caché de {nombre} ({intensidad}){Colors.END}")
            
        if nombre == 'Firefox':
            # Para Firefox, recorremos los perfiles
            for perfil in os.listdir(ruta_base):
                if perfil.endswith('.default-release'):
                    cache_dir = os.path.join(ruta_base, perfil, 'cache2')
                    if os.path.exists(cache_dir):
                        # Eliminar solo archivos antiguos
                        for root, dirs, files in os.walk(cache_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    tiempo_mod = datetime.fromtimestamp(os.path.getmtime(file_path))
                                    if datetime.now() - tiempo_mod > timedelta(days=dias_limite):
                                        file_size = os.path.getsize(file_path)
                                        os.remove(file_path)
                                        espacio_liberado += file_size
                                        archivos_eliminados.append(file_path)
                                except Exception as e:
                                    logger.error(f"Error eliminando {file_path}: {str(e)}")
        else:
            # Para Edge
            for root, dirs, files in os.walk(ruta_base):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        tiempo_mod = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if datetime.now() - tiempo_mod > timedelta(days=dias_limite):
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            espacio_liberado += file_size
                            archivos_eliminados.append(file_path)
                    except Exception as e:
                        logger.error(f"Error eliminando {file_path}: {str(e)}")
    
    # Mostrar resumen detallado
    if archivos_eliminados:
        print(f"\n{Colors.CYAN}Archivos de caché eliminados ({len(archivos_eliminados)}):{Colors.END}")
        for i, archivo in enumerate(archivos_eliminados[:5], 1):
            print(f"{i}. {archivo}")
        if len(archivos_eliminados) > 5:
            print(f"... y {len(archivos_eliminados) - 5} más")
        logger.info(f"Se eliminaron {len(archivos_eliminados)} archivos de cache. Espacio liberado: {bytes_a_mb(espacio_liberado)} MB")
    else:
        logger.info("No se encontraron archivos de cache para eliminar")
                        
    return espacio_liberado

def analizar_disco(solo_detect=False):
    """Identifica archivos grandes y temporales antiguos (solo detección)"""
    print(f"\n{Colors.YELLOW}Analizando disco...{Colors.END}")
    logger.info("Analizando disco...")
    unidades = [unidad.mountpoint for unidad in psutil.disk_partitions() if 'fixed' in unidad.opts]
    
    archivos_grandes = []
    archivos_protegidos = ["pagefile.sys", "hiberfil.sys", "swapfile.sys"]
    
    for unidad in unidades:
        print(f"{Colors.BLUE}Escaneando {unidad}...{Colors.END}")
        logger.info(f"Escaneando unidad {unidad}")
        
        # Solo escanear directorios comunes para ahorrar tiempo
        directorios_comunes = [
            os.path.join(unidad, 'Windows', 'Temp'),
            os.path.join(unidad, 'Users'),
            os.path.join(unidad, 'Program Files'),
            os.path.join(unidad, 'Program Files (x86)'),
            os.path.join(unidad, 'ProgramData')
        ]
        
        for directorio in directorios_comunes:
            if not os.path.exists(directorio):
                continue
                
            for raiz, _, archivos in os.walk(directorio):
                for archivo in archivos:
                    # Saltar archivos protegidos del sistema
                    if archivo.lower() in archivos_protegidos:
                        continue
                        
                    try:
                        ruta_completa = os.path.join(raiz, archivo)
                        tamaño = os.path.getsize(ruta_completa)
                        
                        # Archivos grandes (>100MB)
                        if tamaño > 100 * 1024 * 1024:  # 100MB
                            archivos_grandes.append((ruta_completa, tamaño))
                    except:
                        continue
    
    # Ordenar por tamaño descendente
    archivos_grandes.sort(key=lambda x: x[1], reverse=True)
    
    if not solo_detect:
        print(f"\n{Colors.YELLOW}Archivos grandes detectados (>100MB):{Colors.END}")
        logger.info(f"Archivos grandes detectados: {len(archivos_grandes)}")
        for archivo, tamaño in archivos_grandes[:10]:
            print(f"{bytes_a_mb(tamaño)} MB: {archivo}")
    
    return archivos_grandes

# --- FUNCIONES DE OPTIMIZACIÓN --- #
@retry_on_error()
def ejecutar_cleanmgr():
    """Ejecuta la utilidad de limpieza de disco de Windows"""
    try:
        # Iniciamos cleanmgr y esperamos a que termine
        result = subprocess.run(['cleanmgr', '/sagerun:1'], 
                               check=True, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True, 
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               timeout=300)
        logger.info("cleanmgr ejecutado correctamente")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error en cleanmgr: código {e.returncode}\nSalida error: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("cleanmgr: Timeout de 300 segundos excedido")
        return False
    except Exception as e:
        logger.error(f"Error inesperado en cleanmgr: {str(e)}")
        return False

@retry_on_error()
def optimizar_servicios():
    """Deshabilita servicios innecesarios para mejorar el rendimiento"""
    servicios_deshabilitar = [
        "DiagTrack",  # Servicio de seguimiento de diagnóstico
        "dmwappushservice",  # Servicio de push de WAP
        "MapsBroker",  # Servicio de mapas (si no se usa)
    ]
    
    try:
        exitos = 0
        for servicio in servicios_deshabilitar:
            try:
                # Verificar si el servicio existe
                check = subprocess.run(['sc', 'query', servicio], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      text=True, 
                                      creationflags=subprocess.CREATE_NO_WINDOW,
                                      timeout=30)
                
                if "FAILED 1060" in check.stderr:
                    logger.info(f"Servicio {servicio} no encontrado, omitiendo")
                    continue
                
                # Deshabilitar
                subprocess.run(['sc', 'config', servicio, 'start=', 'disabled'], 
                              check=True, 
                              creationflags=subprocess.CREATE_NO_WINDOW,
                              timeout=30)
                
                # Detener solo si está en ejecución
                if "RUNNING" in check.stdout:
                    subprocess.run(['sc', 'stop', servicio], 
                                  check=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW,
                                  timeout=30)
                    logger.info(f"Servicio {servicio} detenido")
                
                exitos += 1
                logger.info(f"Servicio {servicio} deshabilitado")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error con servicio {servicio}: {e.stderr}")
            except Exception as e:
                logger.error(f"Error inesperado con servicio {servicio}: {str(e)}")
        
        logger.info(f"Servicios optimizados: {exitos}/{len(servicios_deshabilitar)}")
        return f"Servicios optimizados: {exitos}/{len(servicios_deshabilitar)}"
    except Exception as e:
        logger.error(f"Error general en optimizar_servicios: {str(e)}")
        return f"Error general: {str(e)}"

@retry_on_error()
def configurar_alto_rendimiento():
    """Configura el esquema de energía a alto rendimiento"""
    try:
        # Usar método directo con powercfg
        subprocess.run(['powercfg', '/setactive', '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'], 
                      check=True, 
                      creationflags=subprocess.CREATE_NO_WINDOW,
                      timeout=30)
        logger.info("Esquema de alto rendimiento activado")
        return "Esquema de alto rendimiento activado"
    except subprocess.CalledProcessError:
        logger.warning("No se pudo activar alto rendimiento, intentando método alternativo")
        try:
            # Método alternativo para Windows Home
            subprocess.run(['powercfg', '/s', 'SCHEME_MIN'], 
                          check=True, 
                          creationflags=subprocess.CREATE_NO_WINDOW,
                          timeout=30)
            return "Esquema de alto rendimiento activado (alternativo)"
        except Exception as e:
            logger.error(f"Error al activar alto rendimiento: {str(e)}")
            return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return f"Error: {str(e)}"

# --- FUNCIÓN PARA EJECUTAR EL PLAN --- #
def ejecutar_plan_optimizacion(plan):
    """Ejecuta las acciones recomendadas por Phi3-mini"""
    resultados = {}
    
    # Mapeo de nombres descriptivos a nombres técnicos
    mapeo_acciones = {
        "limpieza_temporales": "limpieza_temporales",
        "gestion_programas_inicio": "optimizar_arranque",
        "analisis_disco": "analizar_disco",
        "optimizacion_servicios": "optimizar_servicios",
        "configuracion_energia": "configurar_alto_rendimiento",
        "limpieza_cache_navegadores": "limpiar_cache_navegadores",
        "vaciar_papelera": "vaciar_papelera",
        "ejecutar_cleanmgr": "ejecutar_cleanmgr"
    }
    
    for accion in plan.get('acciones', []):
        accion_tipo = accion['tipo']
        intensidad = accion.get('intensidad', 'media')
        
        # Convertir a nombre técnico
        accion_tecnica = mapeo_acciones.get(accion_tipo.lower(), accion_tipo)
        
        print(f"\n{Colors.YELLOW}>>> Ejecutando: {accion_tipo} -> {accion_tecnica} ({intensidad}){Colors.END}")
        logger.info(f"Ejecutando acción: {accion_tipo} ({accion_tecnica}) con intensidad {intensidad}")
        
        if accion_tecnica == "limpieza_temporales":
            espacio = limpiar_archivos_temporales(intensidad)
            resultados[accion_tipo] = f"Liberados {bytes_a_mb(espacio)} MB"
            
        elif accion_tecnica == "vaciar_papelera":
            if vaciar_papelera():
                resultados[accion_tipo] = "Papelera vaciada"
            else:
                resultados[accion_tipo] = "Error al vaciar papelera"
                
        elif accion_tecnica == "optimizar_arranque":
            resultados[accion_tipo] = optimizar_arranque_auto(intensidad)
            
        elif accion_tecnica == "limpiar_cache_navegadores":
            espacio = limpiar_cache_navegadores(intensidad)
            resultados[accion_tipo] = f"Liberados {bytes_a_mb(espacio)} MB"
            
        elif accion_tecnica == "analizar_disco":
            grandes_archivos = analizar_disco(solo_detect=True)
            print(f"\n{Colors.YELLOW}Archivos grandes detectados:{Colors.END}")
            for archivo, tamaño in grandes_archivos[:5]:
                print(f"{bytes_a_mb(tamaño)} MB: {archivo}")
            resultados[accion_tipo] = "Análisis completado"
        
        elif accion_tecnica == "ejecutar_cleanmgr":
            if ejecutar_cleanmgr():
                resultados[accion_tipo] = "Limpieza de sistema completada"
            else:
                resultados[accion_tipo] = "Error en cleanmgr"
                
        elif accion_tecnica == "optimizar_servicios":
            resultados[accion_tipo] = optimizar_servicios()
            
        elif accion_tecnica == "configurar_alto_rendimiento":
            resultados[accion_tipo] = configurar_alto_rendimiento()
            
        else:
            logger.warning(f"Acción no reconocida: {accion_tipo}")
            resultados[accion_tipo] = "Acción no reconocida"
    
    # Mostrar resumen
    print(f"\n{Colors.GREEN}=== RESUMEN DE OPTIMIZACIÓN ==={Colors.END}")
    for accion, resultado in resultados.items():
        print(f"- {accion}: {resultado}")
    logger.info("Resumen de optimización: " + str(resultados))

# --- FUNCIONES DE OPTIMIZACIÓN AUTOMATIZADAS --- #
@retry_on_error()
def optimizar_arranque_auto(intensidad="media"):
    """Deshabilita programas de inicio automáticamente basado en heurística"""
    try:
        clave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                              r"Software\Microsoft\Windows\CurrentVersion\Run")
        
        deshabilitados = []
        conservados = []
        
        i = 0
        while True:
            try:
                nombre, valor, _ = winreg.EnumValue(clave, i)
                # Heurística: deshabilitar programas poco comunes o de terceros
                if intensidad == "alta" or "update" in nombre.lower() or "cloud" in nombre.lower():
                    winreg.DeleteValue(clave, nombre)
                    deshabilitados.append(nombre)
                    logger.info(f"Deshabilitado programa de inicio: {nombre}")
                else:
                    conservados.append(nombre)
                i += 1
            except OSError:
                break
        
        return f"Deshabilitados: {len(deshabilitados)}, Conservados: {len(conservados)}"
    except Exception as e:
        logger.error(f"Error en optimizar_arranque_auto: {str(e)}")
        return f"Error: {str(e)}"

# --- GENERADOR DE REPORTE OPTIMIZADO --- #
def generar_reporte_sistema():
    """Genera un reporte detallado del sistema para Phi3-mini (optimizado)"""
    reporte = "=== Información del Sistema ===\n"
    reporte += f"Sistema operativo: {platform.system()} {platform.release()}\n"
    
    # Memoria
    mem = psutil.virtual_memory()
    reporte += f"\n--- Memoria ---\n"
    reporte += f"Total: {bytes_a_gb(mem.total)} GB\n"
    reporte += f"Disponible: {bytes_a_gb(mem.available)} GB\n"
    reporte += f"En uso: {mem.percent}%\n"
    
    # Disco (solo resumen)
    reporte += f"\n--- Almacenamiento (resumen) ---\n"
    for particion in psutil.disk_partitions():
        if 'cdrom' in particion.opts or particion.fstype == '':
            continue
        uso = psutil.disk_usage(particion.mountpoint)
        reporte += f"Particion {particion.device} ({particion.mountpoint}):\n"
        reporte += f"  Total: {bytes_a_gb(uso.total)} GB\n"
        reporte += f"  Libre: {bytes_a_gb(uso.free)} GB\n"
        reporte += f"  Uso: {uso.percent}%\n"
    
    # Archivos grandes en temporales
    reporte += f"\n--- Archivos Temporales Grandes (>100MB) ---\n"
    directorios_tmp = [
        os.environ.get('TEMP'),
        os.path.join(os.environ['SystemRoot'], 'Temp'),
        os.path.join(os.environ['LOCALAPPDATA'], 'Temp')
    ]
    
    for directorio in directorios_tmp:
        if not directorio or not os.path.exists(directorio):
            continue
        try:
            for entry in os.scandir(directorio):
                if entry.is_file() and entry.stat().st_size > 100 * 1024 * 1024:
                    reporte += f"- {bytes_a_mb(entry.stat().st_size)} MB: {entry.path}\n"
        except:
            continue
    
    return reporte

# --- FUNCIONES AUXILIARES --- #
def obtener_tamaño_carpeta(ruta):
    total = 0
    for entrada in os.scandir(ruta):
        if entrada.is_file():
            total += entrada.stat().st_size
        elif entrada.is_dir():
            total += obtener_tamaño_carpeta(entrada.path)
    return total

def bytes_a_mb(bytes_size):
    return round(bytes_size / (1024 * 1024), 2)

def bytes_a_gb(bytes_size):
    return round(bytes_size / (1024 * 1024 * 1024), 2)

# --- INTERFAZ PRINCIPAL --- #
def mostrar_menu():
    print(f"\n{Colors.YELLOW}=== OPTIMIZADOR WINDOWS CON PHI3-MINI ===")
    print("1. Limpieza básica (archivos temporales)")
    print("2. Limpieza avanzada (temporales + navegadores)")
    print("3. Vaciar papelera de reciclaje")
    print("4. Optimizar programas de inicio")
    print("5. Analizar espacio en disco")
    print("6. Optimización completa tradicional")
    print("7. Auto-optimización con Phi3-mini (Ollama)")
    print("8. Optimización profunda (todas las funciones)")
    print(f"9. Salir{Colors.END}")

def main():
    if not es_admin():
        print(f"{Colors.RED}Se requieren permisos de administrador{Colors.END}")
        solicitar_admin()
    
    # Verificar si Ollama está disponible
    ollama_disponible = True
    try:
        test_response = requests.get("http://localhost:11434", timeout=5)
        ollama_disponible = test_response.status_code == 200
    except:
        ollama_disponible = False
    
    # Verificar si el modelo está instalado
    modelo_instalado = False
    if ollama_disponible:
        try:
            response = requests.post("http://localhost:11434/api/show", json={"name": MODEL_NAME})
            modelo_instalado = response.status_code == 200
        except:
            modelo_instalado = False
    
    logger.info("Inicio del optimizador")
    while True:
        mostrar_menu()
        opcion = input("\nSeleccione una opción: ")
        logger.info(f"Opción seleccionada: {opcion}")

        if opcion == "1":
            espacio = limpiar_archivos_temporales()
            print(f"\n{Colors.GREEN}✓ Liberados {bytes_a_mb(espacio)} MB{Colors.END}")
            
        elif opcion == "2":
            espacio1 = limpiar_archivos_temporales()
            espacio2 = limpiar_cache_navegadores()
            print(f"\n{Colors.GREEN}✓ Total liberado: {bytes_a_mb(espacio1 + espacio2)} MB{Colors.END}")
            
        elif opcion == "3":
            if vaciar_papelera():
                print(f"\n{Colors.GREEN}✓ Papelera vaciada{Colors.END}")
            else:
                print(f"\n{Colors.RED}✗ Error al vaciar papelera{Colors.END}")
                
        elif opcion == "4":
            resultado = optimizar_arranque_auto()
            print(f"\n{Colors.GREEN}✓ {resultado}{Colors.END}")
            
        elif opcion == "5":
            print("\nAnalizando disco...")
            grandes_archivos = analizar_disco()
                
        elif opcion == "6":
            espacio_temp = limpiar_archivos_temporales()
            espacio_cache = limpiar_cache_navegadores()
            papelera_ok = vaciar_papelera()
            resultado_arranque = optimizar_arranque_auto()
            
            print(f"\n{Colors.GREEN}✓ Optimización completada:{Colors.END}")
            print(f"- Liberados {bytes_a_mb(espacio_temp)} MB en temporales")
            print(f"- Liberados {bytes_a_mb(espacio_cache)} MB en cachés")
            print(f"- Papelera: {'Vaciada' if papelera_ok else 'Error'}")
            print(f"- Inicio: {resultado_arranque}")
            
        elif opcion == "7":
            if not ollama_disponible:
                print(f"{Colors.RED}Ollama no detectado. Por favor instala y ejecuta Ollama primero.{Colors.END}")
                print("Instrucciones: https://ollama.com/download")
                print("Ejecuta 'ollama serve' en una terminal antes de usar esta opción.")
                logger.warning("Ollama no disponible para auto-optimización")
                continue
                
            if not modelo_instalado:
                print(f"{Colors.RED}El modelo {MODEL_NAME} no está instalado.{Colors.END}")
                print(f"Por favor instálalo con: ollama pull {MODEL_NAME}")
                logger.warning(f"Modelo {MODEL_NAME} no instalado")
                continue
                
            auto_optimizar_con_phi3()
            
        elif opcion == "8":
            print(f"{Colors.MAGENTA}\nIniciando optimización profunda...{Colors.END}")
            logger.info("Iniciando optimización profunda")
            
            # Limpieza tradicional
            espacio_temp = limpiar_archivos_temporales("alta")
            espacio_cache = limpiar_cache_navegadores("alta")
            papelera_ok = vaciar_papelera()
            resultado_arranque = optimizar_arranque_auto("alta")
            
            # Optimizaciones profundas
            print(f"{Colors.BLUE}\nEjecutando limpieza del sistema...{Colors.END}")
            cleanmgr_ok = ejecutar_cleanmgr()
            
            print(f"{Colors.BLUE}Optimizando servicios...{Colors.END}")
            servicios_result = optimizar_servicios()
            
            print(f"{Colors.BLUE}Configurando alto rendimiento...{Colors.END}")
            energia_result = configurar_alto_rendimiento()
            
            print(f"\n{Colors.GREEN}✓ Optimización profunda completada:{Colors.END}")
            print(f"- Liberados {bytes_a_mb(espacio_temp)} MB en temporales")
            print(f"- Liberados {bytes_a_mb(espacio_cache)} MB en cachés")
            print(f"- Papelera: {'Vaciada' if papelera_ok else 'Error'}")
            print(f"- Inicio: {resultado_arranque}")
            print(f"- Limpieza sistema: {'Completada' if cleanmgr_ok else 'Error'}")
            print(f"- Servicios: {servicios_result}")
            print(f"- Energía: {energia_result}")
            logger.info("Optimización profunda completada")
            
        elif opcion == "9":
            print("\n¡Hasta luego!")
            logger.info("Fin del optimizador")
            break
            
        else:
            print(f"\n{Colors.RED}Opción inválida{Colors.END}")
            logger.warning(f"Opción inválida: {opcion}")

if __name__ == "__main__":
    # Instrucciones iniciales
    print(f"{Colors.CYAN}Optimizador Windows con Phi3-mini (2.2GB RAM){Colors.END}")
    print(f"Modelo actual: {MODEL_NAME}")
    print("Nota: Para la opción 7, asegúrate de tener Ollama instalado y ejecutando")
    main()