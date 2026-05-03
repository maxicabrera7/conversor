# Conversor Pro (cvt)

Herramienta técnica para la extracción y normalización de datos desde formatos propietarios (.pdf, .pptx, .docx, .xlsx) a Markdown limpio, optimizado para alimentar Modelos de Lenguaje (LLMs).

## 🛠 Capacidades Técnicas

- **Motores de Conversión:**
    - **PDF:** Utiliza `pymupdf4llm` para una extracción con preservación de tablas y marcas[cite: 1].
    - **Office (.pptx, .docx):** Implementado mediante `markitdown` de Microsoft y `python-pptx` para procesar notas del orador[cite: 1].
    - **Excel (.xlsx):** Conversión de hojas de cálculo a tablas Markdown mediante `pandas` y `tabulate`[cite: 1].
- **Procesamiento de Texto:** Limpieza automática de ruido visual, normalización de saltos de línea y eliminación de caracteres nulos mediante expresiones regulares[cite: 1].
- **Interfaz:** Barra de progreso integrada con `tqdm` para el procesamiento de directorios completos[cite: 1].

## 📂 Estructura del Proyecto

- `convertir.py`: Núcleo del script con lógica de reintentos y resolución de rutas inteligentes[cite: 1].
- `venv/`: Entorno virtual local (aislado y fuera del control de versiones).
- `.gitignore`: Configuración estricta para evitar la subida de binarios y basura técnica.
- `errores.log`: Registro automático de fallos de conversión[cite: 1].

## 🔧 Instalación Local

1. Clonar el repositorio en `C:\dev\conversor`.
2. Crear y configurar el entorno virtual:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install pymupdf4llm markitdown python-pptx pandas tqdm tabulate

   ## ⌨️ Integración con PowerShell ($PROFILE)
Añade esta función a tu perfil de Windows PowerShell para ejecutar el conversor desde cualquier ubicación:

function cvt {
    # Control de sincronización con cooldown de 1 día
    $syncFile = "$HOME\.cvt_last_sync"
    $currentDate = Get-Date
    $repoPath = "C:\dev\conversor"

    if (Test-Path $syncFile) {
        try {
            $content = Get-Content $syncFile -Raw
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

    # Ejecución del script
    & "C:\dev\conversor\venv\Scripts\python.exe" "C:\dev\conversor\convertir.py" $args[0]
}

## 🚀 Uso
El script permite procesar archivos individuales o carpetas completas. Crea automáticamente una carpeta MD_NombreDelArchivo para organizar el output y las imágenes extraídas
# Convertir un archivo (la extensión es opcional)
cvt "DocumentoTecnico.pdf"

# Procesar una carpeta completa de archivos Office/PDF
cvt "."