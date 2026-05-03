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

## --- GUÍA DE INSTALACIÓN ---

1. INSTALAR GIT CLI (No solo la App de Escritorio):
Descarga desde: https://git-scm.com/download/win
DURANTE LA INSTALACIÓN: Es CRÍTICO seleccionar la opción:
"Git from the command line and also from 3rd-party software"
Esto permite que PowerShell reconozca el comando 'git'.

2. VERIFICACIÓN:
Abre una PowerShell nueva y escribe:
git --version
Si responde con una versión, el sistema está listo.

3. INSTALAR PYTHON:
Descarga desde: https://python.org
DURANTE LA INSTALACIÓN: Marca la casilla "Add Python to PATH".

4. DESPLIEGUE DEL CONVERSOR:
```powershell
 1. cd C:\dev
    2. git clone https://github.com/maxicabrera7/conversor.git
        3. cd conversor
            4. python -m venv venv
                5. .\venv\Scripts\Activate.ps1
                    6. pip install pymupdf4llm markitdown python-pptx pandas tqdm tabulate
```

5. ⌨️ Integración Global (PowerShell $PROFILE)

Copia este bloque en tu `$PROFILE` para disponer del comando `cvt` globalmente. El script incluye un sistema de sincronización automática con cooldown de 1 día:
```powershell
function cvt {
    $syncFile = "$HOME\.cvt_last_sync"
    $currentDate = Get-Date
    $repoPath = "C:\dev\conversor"

    if (Test-Path $syncFile) {
        try {
            $content = (Get-Content $syncFile -Raw).Trim()
            $lastSync = [DateTime]$content
            if ($currentDate -gt $lastSync.AddDays(1)) {
                if (Test-Path "$repoPath\.git") {
                    Write-Host "[!] Sincronizando cvt..." -ForegroundColor Yellow
                    Push-Location $repoPath; git pull origin main; Pop-Location
                    Get-Date -Format "yyyy-MM-dd HH:mm:ss" | Out-File $syncFile
                }
            }
        } catch { Get-Date -Format "yyyy-MM-dd HH:mm:ss" | Out-File $syncFile }
    } else { Get-Date -Format "yyyy-MM-dd HH:mm:ss" | Out-File $syncFile }

    & "C:\dev\conversor\venv\Scripts\python.exe" "C:\dev\conversor\convertir.py" $args[0]
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