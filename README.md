
# OSINT-EC

Framework de investigación OSINT con módulos plug-and-play y flujo unificado.

## Instalación

### Linux

1) Clonar el repositorio

```
git clone https://github.com/afreireo/osint-ec.git && cd osint-ec
```

2) Instalar dependencias
```
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```
```
sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
```

3) Iniciar la aplicación
```bash
python osint-ec.py
```

### Windows (cmd)
1) Clonar el repositorio
```
git clone https://github.com/afreireo/osint-ec.git && cd osint-ec
```

2) Instalar dependencias

```
python -m venv .venv
.\.venv\Scripts\Activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```
 * Instalar tesseract y añadir al PATH windows
https://docs.coro.net/featured/agent/install-tesseract-windows/

3) Inicar la aplicación 

```
python osint-ec.py
```




## Uso
* Búsqueda en base a una identificación

* Selección de módulos

* Visualización de resultados

## Disclaimer
Este proyecto se ofrece con fines investigativos y educativos. La información se obtiene de fuentes abiertas (OSINT) y su uso, tratamiento y difusión son responsabilidad exclusiva del usuario. Al utilizarlo, el usuario se compromete a respetar los Términos de Uso y la normativa aplicable de cada sitio consultado. En particular, los resultados provenientes del SIAF corresponden a una base de datos de acceso público conforme a los arts. 76.7.d de la Constitución, 13 del COFJ y 421 (inc. segundo) del COIP.