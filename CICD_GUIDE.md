# Guide CI/CD — Corrige Moi Backend

## Vue d'ensemble

Le CI/CD (Continuous Integration / Continuous Deployment) permet de déployer automatiquement
le backend sur le VPS Contabo à chaque fois qu'on pousse du code sur la branche `prod`.

**Flux de travail :**
```
Code modifié en local → git push origin prod → GitHub Actions → Déploiement automatique sur VPS
```

---

## Prérequis

- Repo GitHub avec les branches `main` (développement) et `prod` (production)
- VPS Contabo avec IP `79.143.190.190`, utilisateur `hans`
- Gunicorn configuré comme service systemd (`corrigemoi.service`)

---

## Étape 1 — Créer une clé SSH dédiée au CI/CD

GitHub Actions doit pouvoir se connecter au VPS sans mot de passe.
On génère une paire de clés SSH spécifiquement pour ça.

**Sur le VPS :**

```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions -N ""
```

- `-t ed25519` : algorithme de chiffrement moderne et sécurisé
- `-C "github-actions"` : commentaire pour identifier la clé
- `-f ~/.ssh/github_actions` : nom du fichier de la clé (crée 2 fichiers : clé privée + clé publique)
- `-N ""` : pas de passphrase (obligatoire pour l'automatisation)

Ensuite, ajouter la clé publique aux clés autorisées sur le VPS :

```bash
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
```

Cela permet à quiconque possède la clé privée correspondante de se connecter en SSH au VPS.

Afficher la clé privée (on en aura besoin à l'étape suivante) :

```bash
cat ~/.ssh/github_actions
```

Copier tout le contenu — de `-----BEGIN OPENSSH PRIVATE KEY-----` jusqu'à `-----END OPENSSH PRIVATE KEY-----`.

---

## Étape 2 — Configurer les secrets GitHub

Les secrets GitHub permettent de stocker des informations sensibles (IP, mot de passe, clé SSH)
sans les écrire en clair dans le code.

**Sur GitHub :** Repo → Settings → Secrets and variables → Actions → New repository secret

Créer ces 3 secrets :

| Nom du secret | Valeur |
|---------------|--------|
| `VPS_HOST` | `79.143.190.190` (IP du VPS) |
| `VPS_USER` | `hans` (utilisateur SSH) |
| `VPS_SSH_KEY` | Contenu complet de `~/.ssh/github_actions` (clé privée) |

Ces variables seront accessibles dans le fichier GitHub Actions via `${{ secrets.NOM_SECRET }}`.

---

## Étape 3 — Autoriser le redémarrage de Gunicorn sans mot de passe

GitHub Actions se connecte en tant que `hans`, mais redémarrer un service systemd
nécessite normalement les droits sudo avec mot de passe.
On configure `sudoers` pour autoriser cette commande spécifique sans mot de passe.

**Sur le VPS :**

```bash
sudo visudo
```

Ajouter cette ligne à la fin du fichier :

```
hans ALL=(ALL) NOPASSWD: /bin/systemctl restart corrigemoi
```

- `hans` : l'utilisateur concerné
- `ALL=(ALL)` : depuis n'importe quel terminal, en tant que n'importe quel utilisateur
- `NOPASSWD:` : sans demander de mot de passe
- `/bin/systemctl restart corrigemoi` : uniquement cette commande précise (pas tous les sudo)

---

## Étape 4 — Créer le fichier GitHub Actions

Ce fichier définit ce que GitHub doit faire automatiquement à chaque push sur `prod`.
Il doit être placé dans `.github/workflows/deploy.yml` à la racine du projet.

```yaml
name: Deploy to VPS
```
Nom du workflow, affiché dans l'onglet Actions sur GitHub.

```yaml
on:
  push:
    branches:
      - prod
```
**Déclencheur :** ce workflow se lance uniquement quand on pousse sur la branche `prod`.
Pousser sur `main` ou une autre branche ne déclenche rien.

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
```
Définit un job appelé `deploy` qui s'exécute sur une machine virtuelle Ubuntu
hébergée par GitHub (gratuit jusqu'à 2000 minutes/mois).

```yaml
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
```
Utilise l'action `appleboy/ssh-action` — une action open source qui permet
de se connecter à un serveur SSH et d'exécuter des commandes.

```yaml
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
```
Paramètres de connexion SSH, lus depuis les secrets GitHub configurés à l'étape 2.
Jamais écrits en clair dans le fichier.

```yaml
          script: |
            cd ~/CORRECTION-APP-BACKEND
```
Se déplace dans le dossier du projet sur le VPS.

```yaml
            git pull origin prod
```
Récupère les dernières modifications depuis la branche `prod` sur GitHub.

```yaml
            source venv/bin/activate
```
Active l'environnement virtuel Python du projet.

```yaml
            pip install -r requirements.txt --quiet
```
Installe les nouvelles dépendances si `requirements.txt` a changé.
`--quiet` réduit la verbosité des logs.

```yaml
            python manage.py migrate --noinput
```
Applique les nouvelles migrations de base de données.
`--noinput` évite les confirmations interactives.

```yaml
            python manage.py collectstatic --noinput
```
Regroupe les fichiers statiques (CSS, JS) dans le dossier `staticfiles/`.

```yaml
            sudo systemctl restart corrigemoi
```
Redémarre Gunicorn pour charger le nouveau code.
Fonctionne sans mot de passe grâce à la configuration sudoers de l'étape 3.

```yaml
            echo "Déployé avec succès !"
```
Message de confirmation affiché dans les logs GitHub Actions.

---

## Étape 5 — Créer la branche prod et activer le CI/CD

```bash
# Créer la branche prod depuis main
git checkout -b prod
git push -u origin prod
```

Le premier push crée la branche sur GitHub et déclenche immédiatement le premier déploiement.

---

## Utilisation au quotidien

### Workflow recommandé

```
main (développement) ──→ prod (production)
```

1. Travailler et committer sur `main`
2. Quand une fonctionnalité est prête, merger sur `prod`
3. Le déploiement se fait automatiquement

### Commandes

```bash
# Travailler sur main
git checkout main
# ... modifier le code ...
git add .
git commit -m "feat: nouvelle fonctionnalité"
git push origin main

# Déployer en production
git checkout prod
git merge main
git push origin prod
# → GitHub Actions se déclenche automatiquement
```

### Vérifier le déploiement

Sur GitHub : onglet **Actions** → voir les logs en temps réel.

En cas d'échec, les logs indiquent exactement quelle commande a échoué.

---

## En cas de problème

### Vérifier les logs Gunicorn sur le VPS

```bash
sudo journalctl -u corrigemoi -n 50 --no-pager
cat ~/CORRECTION-APP-BACKEND/logs/gunicorn.log
```

### Redémarrer manuellement

```bash
cd ~/CORRECTION-APP-BACKEND
source venv/bin/activate
git pull origin prod
python manage.py migrate
sudo systemctl restart corrigemoi
```

### Rollback (revenir à une version précédente)

```bash
# Sur le VPS
cd ~/CORRECTION-APP-BACKEND
git log --oneline        # voir les commits
git checkout <commit_id> # revenir à un commit précédent
sudo systemctl restart corrigemoi
```
