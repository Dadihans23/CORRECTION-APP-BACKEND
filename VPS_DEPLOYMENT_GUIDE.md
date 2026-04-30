# Guide de Déploiement Django sur VPS

## Vue d'ensemble

Ce guide explique comment déployer un projet Django REST sur un VPS Linux (Ubuntu).
Il couvre l'installation complète, de la connexion SSH jusqu'à la mise en ligne.

**Stack utilisée :**
- **Django** — framework backend Python
- **Gunicorn** — serveur WSGI qui fait tourner Django en production
- **Nginx** — serveur web qui reçoit les requêtes et les transmet à Gunicorn
- **PostgreSQL** — base de données de production
- **systemd** — gestionnaire de services Linux (maintient Gunicorn actif en permanence)

**Architecture :**
```
Internet → Nginx (port 80/443) → Socket Unix → Gunicorn → Django
```

---

## Étape 1 — Connexion au VPS

```bash
ssh root@TON_IP_VPS
```

Mettre à jour le système dès la première connexion :

```bash
apt update && apt upgrade -y
```

---

## Étape 2 — Installer les dépendances système

```bash
apt install -y \
  python3 python3-pip python3-venv \
  git \
  nginx \
  postgresql postgresql-contrib \
  libpq-dev python3-dev build-essential \
  libjpeg-dev libpng-dev libtiff-dev libfreetype6-dev \
  zlib1g-dev libwebp-dev \
  tesseract-ocr \
  certbot python3-certbot-nginx
```

**Explication des paquets :**
- `python3-venv` : permet de créer des environnements virtuels Python
- `nginx` : serveur web reverse proxy
- `postgresql` : base de données
- `libpq-dev` : headers C nécessaires pour compiler psycopg2
- `libjpeg-dev`, `libpng-dev`... : librairies nécessaires pour compiler Pillow (traitement d'images)
- `tesseract-ocr` : moteur OCR pour l'extraction de texte depuis des images
- `certbot` : outil pour obtenir des certificats SSL gratuits (HTTPS)

---

## Étape 3 — Créer un utilisateur dédié (optionnel mais recommandé)

Ne pas faire tourner l'application en tant que `root` pour des raisons de sécurité.

```bash
adduser deploy
usermod -aG sudo deploy
su - deploy
```

Pour la suite du guide, on utilise l'utilisateur courant (ex: `hans`).

---

## Étape 4 — Cloner le projet

```bash
cd ~
git clone https://github.com/TON_COMPTE/TON_REPO.git NOM_DOSSIER
cd NOM_DOSSIER
```

---

## Étape 5 — Créer l'environnement virtuel Python

```bash
python3 -m venv venv
source venv/bin/activate
```

Le prompt change : `(venv)` apparaît au début de la ligne.
Toutes les commandes suivantes s'exécutent dans cet environnement.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Si Pillow échoue à l'installation :**
```bash
sudo apt install -y libjpeg-dev libpng-dev zlib1g-dev
pip install "Pillow>=10.0.0"
```

**Si le requirements.txt est encodé en UTF-16 (généré depuis Windows) :**
```bash
# Vérifier l'encodage
file requirements.txt

# Si UTF-16, le convertir
python3 -c "
content = open('requirements.txt', encoding='utf-16').read()
open('requirements.txt', 'w', encoding='utf-8').write(content)
"
```

---

## Étape 6 — Configurer PostgreSQL

```bash
sudo -u postgres psql
```

Dans le shell psql :

```sql
CREATE DATABASE nom_base;
CREATE USER nom_user WITH PASSWORD 'mot_de_passe_fort';
GRANT ALL PRIVILEGES ON DATABASE nom_base TO nom_user;

-- Nécessaire sur PostgreSQL 15+ (Ubuntu 23+)
GRANT ALL ON SCHEMA public TO nom_user;
ALTER DATABASE nom_base OWNER TO nom_user;
\q
```

---

## Étape 7 — Créer le fichier .env

```bash
nano ~/NOM_DOSSIER/.env
```

```env
SECRET_KEY=cle-secrete-longue-et-aleatoire
DEBUG=False
DATABASE_URL=postgres://nom_user:mot_de_passe@localhost:5432/nom_base
VPS_HOST=TON_IP_VPS

# Clés API spécifiques au projet
GEMINI_API_KEY=...
```

**Générer une SECRET_KEY solide :**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

> Ne jamais mettre `DEBUG=True` en production.
> Ne jamais committer le fichier `.env` sur GitHub (ajouter `.env` dans `.gitignore`).

---

## Étape 8 — Adapter settings.py pour la production

### Base de données dynamique

Remplacer la config SQLite par :

```python
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
    )
}
```

Avec `DATABASE_URL` dans le `.env`, Django bascule automatiquement sur PostgreSQL.
Sans `DATABASE_URL`, il reste sur SQLite (pratique pour le développement local).

### ALLOWED_HOSTS dynamique

```python
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    os.getenv('VPS_HOST', ''),
    os.getenv('VPS_DOMAIN', ''),
]
ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h]
```

---

## Étape 9 — Migrations et fichiers statiques

```bash
cd ~/NOM_DOSSIER
source venv/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser  # optionnel
```

- `migrate` : crée les tables en base de données
- `collectstatic` : regroupe tous les fichiers CSS/JS dans `staticfiles/`
- `createsuperuser` : crée un compte administrateur

**Tester que Django démarre correctement :**
```bash
gunicorn --bind 0.0.0.0:8000 nom_projet.wsgi:application
# Si OK → Ctrl+C pour arrêter
```

---

## Étape 10 — Configurer Gunicorn comme service systemd

Gunicorn doit rester actif en permanence et redémarrer automatiquement si le serveur reboot.
On le configure comme un service Linux via systemd.

```bash
sudo nano /etc/systemd/system/monprojet.service
```

```ini
[Unit]
Description=Mon Projet Django
After=network.target

[Service]
User=hans
Group=www-data
WorkingDirectory=/home/hans/NOM_DOSSIER
EnvironmentFile=/home/hans/NOM_DOSSIER/.env
RuntimeDirectory=monprojet
ExecStart=/home/hans/NOM_DOSSIER/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/monprojet/monprojet.sock \
    --log-file /home/hans/NOM_DOSSIER/logs/gunicorn.log \
    --access-logfile /home/hans/NOM_DOSSIER/logs/access.log \
    nom_projet.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

**Explication des paramètres clés :**
- `EnvironmentFile` : charge les variables du `.env` automatiquement
- `RuntimeDirectory=monprojet` : crée `/run/monprojet/` avec les bonnes permissions (résout les erreurs "Permission denied" sur le socket)
- `--workers 3` : nombre de processus Gunicorn (règle : 2 × CPU + 1)
- `--bind unix:/run/...sock` : utilise un socket Unix (plus rapide que TCP pour la communication Nginx ↔ Gunicorn)
- `Restart=always` : redémarre automatiquement si Gunicorn crash

```bash
# Créer le dossier logs
mkdir -p ~/NOM_DOSSIER/logs

# Activer et démarrer le service
sudo systemctl daemon-reload
sudo systemctl enable monprojet
sudo systemctl start monprojet
sudo systemctl status monprojet
```

---

## Étape 11 — Configurer Nginx

Nginx reçoit toutes les requêtes HTTP et les transmet à Gunicorn via le socket Unix.
Il sert aussi directement les fichiers statiques et media sans passer par Django.

```bash
sudo nano /etc/nginx/sites-available/monprojet
```

```nginx
server {
    listen 80;
    server_name TON_IP_VPS ton-domaine.com;

    client_max_body_size 20M;

    location /static/ {
        alias /home/hans/NOM_DOSSIER/staticfiles/;
    }

    location /media/ {
        alias /home/hans/NOM_DOSSIER/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/monprojet/monprojet.sock;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }
}
```

**Explication :**
- `client_max_body_size 20M` : autorise les uploads jusqu'à 20MB
- `location /static/` : Nginx sert les fichiers statiques directement (sans passer par Django)
- `location /media/` : idem pour les fichiers uploadés par les utilisateurs
- `proxy_pass` : transmet toutes les autres requêtes à Gunicorn via le socket

```bash
# Activer la config
sudo ln -s /etc/nginx/sites-available/monprojet /etc/nginx/sites-enabled/

# Vérifier la syntaxe
sudo nginx -t

# Redémarrer Nginx
sudo systemctl restart nginx
```

---

## Étape 12 — Configurer le pare-feu

```bash
sudo ufw allow 22    # SSH (obligatoire, sinon tu te bloques)
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
sudo ufw status
```

---

## Étape 13 — SSL / HTTPS (si tu as un nom de domaine)

```bash
sudo certbot --nginx -d ton-domaine.com
sudo systemctl reload nginx
```

Certbot modifie automatiquement la config Nginx pour ajouter le HTTPS.
Le certificat se renouvelle automatiquement tous les 90 jours.

---

## Commandes utiles au quotidien

### Voir les logs

```bash
# Logs Gunicorn
cat ~/NOM_DOSSIER/logs/gunicorn.log
cat ~/NOM_DOSSIER/logs/access.log

# Logs systemd (en temps réel)
sudo journalctl -u monprojet -f

# Logs Nginx
sudo tail -f /var/log/nginx/error.log
```

### Redémarrer les services

```bash
sudo systemctl restart monprojet   # Redémarrer Gunicorn
sudo systemctl restart nginx       # Redémarrer Nginx
```

### Mise à jour manuelle du code

```bash
cd ~/NOM_DOSSIER
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart monprojet
```

### Script de déploiement rapide

Créer un fichier `deploy.sh` à la racine du projet :

```bash
#!/bin/bash
cd ~/NOM_DOSSIER
git pull
source venv/bin/activate
pip install -r requirements.txt --quiet
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart monprojet
echo "Déployé !"
```

```bash
chmod +x ~/deploy.sh
# Utilisation : ~/deploy.sh
```

---

## Problèmes fréquents et solutions

### "Permission denied" sur le socket

```bash
# Ajouter l'utilisateur au groupe www-data
sudo usermod -aG www-data TON_USER
# Utiliser RuntimeDirectory= dans le service systemd (voir étape 10)
```

### "502 Bad Gateway" Nginx

```bash
# Vérifier que Gunicorn tourne
sudo systemctl status monprojet

# Vérifier que le socket existe
ls -la /run/monprojet/

# Voir les logs d'erreur
cat ~/NOM_DOSSIER/logs/gunicorn.log
```

### "permission denied for schema public" PostgreSQL

```bash
sudo -u postgres psql
```
```sql
GRANT ALL ON SCHEMA public TO nom_user;
ALTER DATABASE nom_base OWNER TO nom_user;
```

### Pillow ne s'installe pas

```bash
sudo apt install -y libjpeg-dev libpng-dev zlib1g-dev libfreetype6-dev
pip install "Pillow>=10.0.0"
```

### requirements.txt illisible (encodage UTF-16 depuis Windows)

Réécrire le fichier en UTF-8 proprement depuis la machine Windows :

```python
python -c "
content = '''Django==4.2.7
gunicorn==23.0.0
...
'''
with open('requirements.txt', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
"
```

---

## Résumé de l'architecture finale

```
[Client / App Mobile]
        ↓ HTTP/HTTPS
[Nginx — port 80/443]
        ↓ Socket Unix
[Gunicorn — workers]
        ↓ WSGI
[Django Application]
        ↓
[PostgreSQL Database]
```

- **Nginx** gère les connexions entrantes, le SSL, et les fichiers statiques
- **Gunicorn** fait tourner Django avec plusieurs workers en parallèle
- **systemd** maintient Gunicorn actif et le redémarre si nécessaire
- **PostgreSQL** stocke toutes les données de l'application
- **Le fichier .env** contient tous les secrets et n'est jamais commité sur Git
