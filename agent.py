import os
import json
import requests
import smtplib
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from google.genai import types

# 1. CONFIGURATION DES CLÉS (Récupérées de manière sécurisée)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")      # Votre adresse e-mail d'envoi (ex: Gmail)
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")  # Votre mot de passe d'application
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")  # L'adresse où vous voulez recevoir l'alerte

client = genai.Client(api_key=GEMINI_API_KEY)

# Liens des comparateurs à surveiller (Exemples Runnea)
URLS_A_CHERCHER = [
    {"modele": "Rocket X 3", "url": "https://www.runnea.fr/chaussures-running/hoka/rocket-x-3/1056465/"},
    {"modele": "Tecton X 3", "url": "https://ledenicheur.fr/product.php?p=12270258"} # Exemple Tecton sur LeDénicheur
]

# 2. FONCTION DE LECTURE DU SITE
def lire_page(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)[:10000] # On prend les 10000 premiers caractères
    except Exception as e:
        print(f"Erreur de lecture sur {url} : {e}")
        return ""

# 3. ANALYSE PAR L'IA GEMINI
def analyser_texte_ia(texte, modele_attendu):
    prompt = f"""
    Tu es un agent de recherche de bons plans. Analyse ce texte issu d'un comparateur de prix pour la chaussure : {modele_attendu}.
    Tu dois vérifier si le modèle est disponible dans la taille "41 1/3" (ou 41.33 ou 41 2/3 selon les arrondis des sites marchands listés).
    
    Renvoie UNIQUEMENT un objet JSON avec cette structure :
    {{
        "bon_plan_detecte": true ou false,
        "meilleur_prix_trouve": 0.0,
        "taille_disponible": true ou false,
        "marchand": "Nom de la boutique la moins chère",
        "resume": "Explication en une phrase"
    }}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt + "\nTexte du site :\n" + texte,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Erreur Gemini : {e}")
        return None

# 4. ENVOI DE L'ALERTE EMAIL
def envoyer_alerte_email(modele, prix, marchand, url):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("⚠️ Configuration email manquante. Impossible d'envoyer l'alerte.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"🔥 ALERTE PROMO HOKA : {modele} à {prix}€ !"

    corps_mail = f"""
    Bonjour,
    
    Votre agent IA a détecté un bon plan qui correspond à vos critères !
    
    - Modèle : HOKA {modele}
    - Prix : {prix} €
    - Boutique : {marchand}
    - Taille demandée : 41 1/3 (Confirmée disponible)
    
    Lien pour vérifier et acheter : {url}
    
    Bonne course !
    Votre Robot Hoka
    """
    msg.attach(MIMEText(corps_mail, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print(f"📧 Email d'alerte envoyé pour la {modele} !")
    except Exception as e:
        print(f"❌ Échec de l'envoi de l'email : {e}")

# 5. EXECUTION PRINCIPALE
def run():
    print("🚀 Démarrage de la vérification quotidienne...")
    for item in URLS_A_CHERCHER:
        print(f"Analyse en cours pour : {item['modele']}...")
        texte_site = lire_page(item['url'])
        
        if not texte_site:
            continue
            
        resultat = analyser_texte_ia(texte_site, item['modele'])
        
        if resultat:
            print(f"-> Résultat : {resultat['resume']}")
            prix = resultat.get('meilleur_prix_trouve', 999)
            taille_ok = resultat.get('taille_disponible', False)
            
            # Application de vos seuils de prix
            est_une_affaire = False
            if item['modele'] == "Rocket X 3" and prix <= 170.0 and taille_ok:
                est_une_affaire = True
            elif item['modele'] == "Tecton X 3" and prix <= 160.0 and taille_ok:
                est_une_affaire = True
                
            if est_une_affaire:
                envoyer_alerte_email(item['modele'], prix, resultat.get('marchand'), item['url'])
            else:
                print("❌ Pas de promo ou taille indisponible pour le moment.")

if __name__ == "__main__":
    run()
