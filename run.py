"""Servidor de desarrollo local. En producción (Vercel) se usa api/index.py."""
import os

from dotenv import load_dotenv

load_dotenv()

from library import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_ENV") != "production", port=int(os.environ.get("PORT", 5000)))
