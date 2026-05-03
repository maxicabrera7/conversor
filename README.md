# Conversor Pro (cvt)

Herramienta técnica de alto rendimiento para la extracción y normalización de datos desde formatos propietarios (.pdf, .pptx, .docx, .xlsx) a Markdown limpio, optimizado para alimentar Modelos de Lenguaje (LLMs).

## 🛠 Capacidades Técnicas

*   **Motores de Conversión**:
    *   **PDF**: Utiliza `pymupdf4llm` para una extracción técnica que preserva tablas y marcas de formato.
    *   **Office (.pptx, .docx)**: Implementado mediante `markitdown` de Microsoft y `python-pptx` para capturar incluso las notas del orador en diapositivas.
    *   **Excel (.xlsx)**: Conversión de cada hoja de cálculo a tablas Markdown independientes mediante `pandas` y `tabulate`.
*   **Procesamiento de Texto**: El script aplica filtros mediante expresiones regulares para eliminar ruido visual, normalizar espaciados (máximo dos saltos de línea) y limpiar caracteres nulos.
*   **Resiliencia**: Incluye una lógica de reintentos automáticos (`MAX_REINTENTOS = 2`) con pausas de seguridad para evitar bloqueos por archivos en uso.
*   **Interfaz**: Sistema de barras de progreso mediante `tqdm` para el procesamiento masivo de directorios, configurable mediante el flag `--quiet`.

## 📂 Estructura del Proyecto

*   `convertir.py`: Núcleo del script con lógica de resolución inteligente de rutas y manejo de errores.
*   `venv/`: Entorno virtual aislado con todas las dependencias instaladas (Excluido de Git vía .gitignore).
*   `.gitignore`: Configuración de filtrado para evitar la subida de binarios, caché de Python y basura técnica.
*   `errores.log`: Registro automático de fallos detallados generado en el directorio de ejecución.

## 🔧 Instalación y Configuración Local

1. Clonar el repositorio en `C:\dev\conversor`.
2. Crear el entorno virtual e instalar la suite de dependencias requeridas:
```python
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## ⌨️ Integración Global (PowerShell $PROFILE)

Copia este bloque en tu `$PROFILE` para disponer del comando `cvt` globalmente. El script incluye un sistema de sincronización automática con cooldown de 1 día:
```powershell
# --- COPIAR ESTO EN EL notepad $PROFILE DE POWERSHELL ---

# 1. Definir la ruta donde se clonó el proyecto
$PATH_UNLAR = "C:\ruta\donde\esta\el\repo"

# 2. Función de sincronización inteligente (Si no existe, crearla)
if (-not (Get-Command Invoke-LazySync -ErrorAction SilentlyContinue)) {
    function Invoke-LazySync {
        param($repoPath, $repoName, $days = 1)
        $sFile = Join-Path $HOME ".cvt_sync_$repoName"
        $now = Get-Date
        if (Test-Path $sFile) {
            try {
                $last = [DateTime](Get-Content $sFile -Raw)
                if ($now -lt $last.AddDays($days)) { return }
            } catch { }
        }
        if (Test-Path (Join-Path $repoPath ".git")) {
            Write-Host "[!] Sincronizando $repoName..." -ForegroundColor Yellow
            Push-Location $repoPath; git pull origin main; Pop-Location
            $now.ToString("yyyy-MM-dd HH:mm:ss") | Out-File $sFile
        }
    }
}

# 3. Comando de ejecución
function cvt {
    Invoke-LazySync $PATH_UNLAR "convertir"
    $py = Join-Path $PATH_UNLAR "vent\Scripts\python.exe"
    $sc = Join-Path $PATH_UNLAR "convertir.py"
    if (Test-Path $py) { & $py $sc $args[0] } else { Write-Error "Entorno virtual no encontrado." }
}
```

## 🚀 Guía de Uso

El script resuelve rutas de forma inteligente (detecta archivos aunque omitas la extensión) y organiza el contenido en carpetas `MD_` dedicadas para preservar las imágenes extraídas.

```powershell
# Convertir un archivo específico
cvt "Reporte_Trimestral.pdf"

# Procesar todos los archivos compatibles en una carpeta completa
cvt "C:\dev\documentacion_cliente"
```

---
**Protocolo de Mantenimiento**: Este proyecto se rige por el principio de optimización radical. Las conversiones fallidas se registran en `errores.log` para auditoría posterior.