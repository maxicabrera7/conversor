# Conversor Pro (cvt)

Herramienta técnica de alto rendimiento para la extracción, limpieza inteligente y normalización de documentos (.pdf, .pptx, .docx, .xlsx) a Markdown limpio, optimizado para alimentar Modelos de Lenguaje (LLMs).

El pipeline opera en cuatro módulos independientes: extracción bruta → limpieza por IA → unificación → salida final.

## 🛠 Capacidades Técnicas

### Motores de Conversión (`convertir.py`)
- **PDF**: `pymupdf4llm` — extracción técnica con preservación de tablas, imágenes y formato.
- **PowerPoint (.pptx)**: `python-pptx` — estructurado por diapositivas con notas del orador en blockquotes.
- **Word (.docx)**: `markitdown` de Microsoft — conversión directa a Markdown.
- **Excel (.xlsx)**: `pandas` + `tabulate` — cada hoja como tabla Markdown independiente.

### Limpieza por IA (`api.py`)
- Utiliza **Gemini 2.5 Flash** via `google-genai` SDK para eliminar ruido de OCR, encabezados repetitivos y basura visual.
- Fragmentación en bloques de ~3250 palabras con **ventana de solapamiento** (sliding window) para no cortar conceptos en los bordes.
- Sistema de reintentos con backoff exponencial para manejar el rate limit del tier gratuito (Error 429).
- Fidelidad absoluta: el modelo tiene instrucciones estrictas de no resumir ni parafrasear.

### Unificación (`unificador.py`)
- Fusiona los bloques procesados en un único documento coherente.
- Elimina redundancias de H1 y solapamientos entre bloques.
- Normaliza el espaciado final del documento.

### Orquestador (`main.py`)
- Interfaz de control que coordina los cuatro módulos.
- Sistema de checkpoints: detecta bloques ya procesados para reanudar sin desperdiciar cuota de API.
- Flag `--no-img` para omitir la extracción de imágenes y reducir el volumen de datos.

## 📂 Estructura del Proyecto

```
conversor/
├── main.py          # Orquestador central (punto de entrada de cvt)
├── convertir.py     # Motor de extracción multi-formato
├── api.py           # Cliente Gemini para limpieza por IA
├── unificador.py    # Ensamblador del documento final
├── requirements.txt
├── .gitignore
└── venv/            # Excluido de Git
```

**Salidas generadas** (excluidas de Git):
- `MD_<nombre>/` — Markdown crudo extraído por `convertir.py`
- `temp_<nombre>/` — Bloques limpios por `api.py` (checkpoint de caché)
- `<nombre>_LIMPIO.md` — Documento final ensamblado

## 🔧 Instalación

```powershell
git clone <repo> C:\dev\conversor
cd C:\dev\conversor
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Variable de entorno requerida** (configurar una sola vez):
```powershell
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "tu-key-aqui", "User")
```

La API key se obtiene en [aistudio.google.com/apikey](https://aistudio.google.com/apikey) en un proyecto **sin billing activado** para acceder al tier gratuito.

## ⌨️ Integración Global (PowerShell `$PROFILE`)

```powershell
$PATH_CVT = "C:\dev\conversor"

function Invoke-LazySync {
    param($repoPath, $repoName)
    $sFile = Join-Path $HOME ".cvt_sync_$repoName"
    $now = Get-Date
    $needsSync = $false
    if (Test-Path $sFile) {
        try {
            $lastSync = [DateTime](Get-Content $sFile -Raw)
            if ($now -gt $lastSync.AddDays(1)) { $needsSync = $true }
        } catch { $needsSync = $true }
    } else { $needsSync = $true }
    if ($needsSync -and (Test-Path (Join-Path $repoPath ".git"))) {
        Write-Host "[!] Sincronizando $repoName..." -ForegroundColor Yellow
        Push-Location $repoPath
        git pull origin main
        Pop-Location
        $now.ToString("yyyy-MM-dd HH:mm:ss") | Out-File $sFile
    }
}

function cvt {
    Invoke-LazySync $PATH_CVT "conversor"
    $python = Join-Path $PATH_CVT "venv\Scripts\python.exe"
    $script  = Join-Path $PATH_CVT "main.py"
    if (Test-Path $python) {
        & $python $script $args[0]
    } else {
        Write-Error "Entorno virtual no encontrado en $PATH_CVT"
    }
}
```

## 🚀 Guía de Uso

```powershell
# Procesar un archivo (genera <nombre>_LIMPIO.md en el mismo directorio)
cvt "Apunte_Termodinamica.pdf"

# Omitir extracción de imágenes (más rápido, menor tamaño)
cvt "Apunte_Termodinamica.pdf" --no-img

# Procesar todos los archivos compatibles de una carpeta
cvt "C:\Universidad\Materia\"
```

> **Nota sobre el tier gratuito**: Gemini 2.5 Flash tiene límites de requests por minuto. El pipeline incluye pausas automáticas entre bloques y reintentos con backoff para operar dentro de esos límites sin intervención manual.

---
**Protocolo de Mantenimiento**: Las conversiones fallidas se registran en `errores.log`. Los bloques ya procesados por la IA se cachean en `temp_<nombre>/` para que ante un corte de cuota puedas reanudar sin reprocesar desde cero.