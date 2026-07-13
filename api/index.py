"""
Punto de entrada para el runtime Python (WSGI) de Vercel.

Vercel detecta automáticamente cualquier variable `app` de tipo WSGI en
`api/*.py` y la expone como función serverless. Todas las rutas se
enrutan aquí gracias a la regla de reescritura definida en `vercel.json`.
"""
import os
import sys

# Permite importar el paquete `library` situado en la raíz del repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library import create_app

app = create_app()
