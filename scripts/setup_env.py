"""Create local configuration without displaying or overwriting a secret."""
from pathlib import Path
from secrets import token_urlsafe

root = Path(__file__).resolve().parent.parent
target = root / ".env"
if target.exists():
    print(".env ya existe; se conserva sin cambios.")
else:
    value = (root / ".env.example").read_text().replace("replace-with-a-random-local-secret", token_urlsafe(50))
    target.write_text(value)
    target.chmod(0o600)
    print(".env creado con una clave local aleatoria.")
