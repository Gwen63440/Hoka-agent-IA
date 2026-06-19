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
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")      
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")  
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")  

# Liens des comparateurs à surveiller
URLS_A_CHERCHER = [
    {
        "modele": "Rocket X 3",
        "url": "https://ledenicheur.fr/search?search=Hoka%20Rocket%20X%203"
    },
    {
        "modele": "Rocket X 3",
        "url": "https://www.runnea.fr/chaussures-running/hoka/rocket-x-3/1056465/"
    },
    {
        "modele": "Rocket X 3",
        "url": "https://www.lepape.com/catalogsearch/result/?q=hoka+rocket+x+3"
    },
    {
        "modele": "Tecton X 3",
        "url": "https://ledenicheur.fr/search?search=Hoka%20Tecton%20X%203"
    },
    {
        "modele": "Tecton X 3",
        "url": "https://www.runnea.fr/chaussures-running/hoka/tecton-x-3/1057000/"
    },
    {
        "modele": "Tecton X 3",
        "url": "https://www.lepape.com/catalogsearch/result/?q=hoka+tecton+x+3"
    }
]

def lire_page(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Page inaccessible (Code {response.status_code}) pour : {url}")
            return ""
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)[:10000]
    except Exception as e:
        print(f"⚠️ Erreur de lecture sur {url} : {e}")
        return ""

def analyser_texte_ia(client, texte, modele_attendu):
    prompt = f"""
    Tu es un agent de recherche de bons plans. Analyse ce texte issu d'un comparateur de prix pour la chaussure : {modele_attendu}.
    Tu dois vérifier si le modèle est disponible dans la taille "41 1/3" (ou 41.33).
    
    Renvoie UNIQUEMENT un objet JSON avec cette structure :
    {{
        "bon_plan_detecte": true ou false,
        "meilleur_prix_trouve": 0.0,
        "taille_disponible": true ou false,
        "marchand": "Nom de la boutique",
        "resume": "Explication courte"
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
        print(f"⚠️ Erreur d'analyse Gemini : {e}")
        return None

def envoyer_alerte_email(modele, prix, marchand, url):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("⚠️ Configuration email manquante (SENDER ou PASSWORD).")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"🔥 ALERTE PROMO HOKA : {modele} à {prix}€ !"

    corps_mail = f"Un bon plan a été détecté !\n\n- Modèle : HOKA {modele}\n- Prix : {prix} €\n- Boutique : {marchand}\n- Taille : 41 1/3\n\nLien : {url}"
    msg.attach(MIMEText(corps_mail, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print(f"📧 Email envoyé avec succès pour {modele} !")
    except Exception as e:
        print(f"⚠️ Échec de l'envoi de l'email : {e}")

def run():
    print("🚀 Démarrage de la vérification...")
    
    if not GEMINI_API_KEY:
        print("❌ ERREUR CRITIQUE : La clé GEMINI_API_KEY est introuvable. Vérifiez vos Secrets GitHub.")
        exit(1)
        
    client = genai.Client(api_key=GEMINI_API_KEY)

    for item in URLS_A_CHERCHER:
        print(f"\n🔍 Analyse de : {item['modele']} sur {item['url'][:40]}...")
        texte_site = lire_page(item['url'])
        
        if not texte_site or len(texte_site) < 200:
            print("❌ Contenu de la page vide ou trop court. Passage au site suivant.")
            continue
            
        resultat = analyser_texte_ia(client, texte_site, item['modele'])
        
        if resultat:
            # Sécurité .get() pour éviter les crashs si l'IA oublie une information
            resume = resultat.get('resume', 'Aucun résumé')
            prix = resultat.get('meilleur_prix_trouve', 999.0)
            taille_ok = resultat.get('taille_disponible', False)
            marchand = resultat.get('marchand', 'Inconnu')
            
            print(f"-> Réponse IA : {resume} (Prix détecté : {prix}€)")
            
            est_une_affaire = False
            if item['modele'] == "Rocket X 3" and prix <= 170.0 and taille_ok:
                est_une_affaire = True
            elif item['modele'] == "Tecton X 3" and prix <= 160.0 and taille_ok:
                est_une_affaire = True
                
            if est_une_affaire:
                print("🚨 CRITÈRES VALIDES ! Envoi de l'e-mail...")
                envoyer_alerte_email(item['modele'], prix, marchand, item['url'])
            else:
                print("❌ Les critères de prix ou de taille ne sont pas cochés.")

if __name__ == "__main__":
    run()
