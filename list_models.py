import os
from dotenv import load_dotenv

load_dotenv()
# Remplace par ta vraie clé dans .env
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

print("Listing des modèles disponibles pour toi :")
print("-" * 30)

for m in genai.list_models():
    # On filtre pour ne garder que ceux qui génèrent du texte/chat
    if 'generateContent' in m.supported_generation_methods:
        print(f"Nom: {m.name}")

print("-" * 30)
