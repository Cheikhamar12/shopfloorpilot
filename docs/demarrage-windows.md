# Démarrer ShopFloorPilot sous Windows (pas à pas)

On travaille dans **WSL2** (un vrai Linux Ubuntu intégré à Windows). C'est ce qu'utilise déjà
Docker Desktop, et c'est le même système que la CI GitHub Actions : ce qui marche chez toi
marchera dans la CI.

> Chaque étape se termine par une **vérification**. Ne passe à la suivante que si elle est OK.

---

## Étape 0 — Installer les outils (une seule fois, ~30 min)

### 0.1 WSL2 + Ubuntu
Dans **PowerShell en administrateur** :
```powershell
wsl --install -d Ubuntu
```
Redémarre le PC, ouvre l'application **Ubuntu** depuis le menu Démarrer, choisis un nom
d'utilisateur et un mot de passe Linux.

✅ Vérification (dans PowerShell) : `wsl -l -v` affiche `Ubuntu` avec `VERSION 2`.

### 0.2 Docker Desktop
1. Installe Docker Desktop depuis le site officiel de Docker.
2. Paramètres → *General* : coche **Use the WSL 2 based engine**.
3. Paramètres → *Resources* → *WSL integration* : active **Ubuntu**.

✅ Vérification (dans le terminal **Ubuntu**) : `docker run --rm hello-world` affiche « Hello from Docker! ».

### 0.3 Outils Linux (dans le terminal Ubuntu)
```bash
sudo apt update && sudo apt install -y make git unzip curl
curl -LsSf https://astral.sh/uv/install.sh | sh     # installe uv (gestionnaire Python)
source ~/.bashrc
```
✅ Vérification : `make --version`, `git --version` et `uv --version` répondent tous.

### 0.4 Git : ton identité et la connexion à GitHub
```bash
git config --global user.name "Ton Nom"
git config --global user.email "ton-email-github@exemple.com"
git config --global init.defaultBranch main
git config --global core.autocrlf input   # évite les fins de ligne Windows (CRLF) dans le dépôt
```
Pour pousser sur GitHub, le plus simple est la CLI GitHub :
```bash
sudo apt install -y gh
gh auth login        # choisis GitHub.com, HTTPS, et connecte-toi via le navigateur
```
✅ Vérification : `gh auth status` indique que tu es connecté.

### 0.5 VS Code (recommandé)
Installe VS Code sous Windows, puis l'extension **WSL**. Depuis le terminal Ubuntu,
`code .` ouvrira le dossier courant dans VS Code, connecté à Linux.

---

## Étape 1 — Mettre le code dans ton dépôt

> Important : travaille dans ton dossier Linux (`~`), **pas** dans `/mnt/c/...`.
> Sur le disque Windows, Docker et Git sont 5 à 10 fois plus lents.

1. Clone ton dépôt GitHub vide :
   ```bash
   cd ~
   git clone https://github.com/<ton-compte>/shopfloorpilot.git
   cd shopfloorpilot
   ```
2. Copie le zip téléchargé (dans `Téléchargements`) et extrais-le dans le dépôt :
   ```bash
   cp /mnt/c/Users/<TonNomWindows>/Downloads/shopfloorpilot-semaine1.zip /tmp/
   unzip -o /tmp/shopfloorpilot-semaine1.zip -d /tmp/
   cp -r /tmp/shopfloorpilot/. .
   ```

✅ Vérification : `ls -a` montre `Makefile`, `docker-compose.yml`, `pyproject.toml`, `src`, `tests`, `.github`…

---

## Étape 2 — Installer l'environnement Python

```bash
uv lock          # fige les versions exactes des dépendances dans uv.lock
make install     # crée .venv, installe les dépendances et les hooks pre-commit
```
✅ Vérification : `make check` se termine par « 8 passed ».

---

## Étape 3 — Démarrer la base de données et le stockage

Docker Desktop doit être lancé.
```bash
make up
```
La première fois, Docker télécharge les images (quelques minutes). `make up` crée aussi
le fichier `.env` à partir de `.env.example` : ouvre-le et change `POSTGRES_PASSWORD` et `S3_SECRET_KEY`.

✅ Vérifications :
- `make ps` : `postgres` et `seaweedfs` sont *healthy*.
- `make psql`, puis tape `\dx` : la ligne `vector` apparaît. Quitte avec `\q`.
- `make buckets` : le bucket `raw` apparaît.
- Ouvre http://localhost:8888 dans ton navigateur Windows : l'interface du filer SeaweedFS
  affiche le dossier `buckets/raw`.

---

## Étape 4 — Générer les données

```bash
make data
```
✅ Vérification : 7 fichiers CSV dans `data/` (`ls data`). Ils ne sont pas commités : le
`.gitignore` les exclut, on les régénère à la demande.

---

## Étape 5 — Premier commit et premier push

```bash
git add .
git status               # vérifie qu'il n'y a NI .env NI data/*.csv dans la liste
git commit -m "chore: socle du dépôt (docker compose, make, CI, générateur de données)"
git push -u origin main
```
Le hook pre-commit tourne au moment du commit (ruff, mypy, scan de secrets). S'il modifie
des fichiers, refais `git add .` puis le même `git commit`.

✅ Vérification : sur GitHub, onglet **Actions**, le workflow « CI » passe au vert (3 jobs).

---

## Commandes du quotidien

| Commande | Rôle |
| --- | --- |
| `make help` | Liste toutes les commandes |
| `make up` / `make down` | Démarre / arrête les services |
| `make reset` | Arrête et **efface** les données de la base (repartir de zéro) |
| `make check` | Lint + typage + tests, comme la CI |
| `make format` | Corrige automatiquement le style |

## Problèmes fréquents

- **`docker: command not found` dans Ubuntu** : Docker Desktop n'est pas lancé, ou
  l'intégration WSL n'est pas activée pour Ubuntu (étape 0.2).
- **`port is already allocated`** : un autre Postgres tourne déjà sur le port 5432. Change
  `POSTGRES_PORT=5433` dans `.env`.
- **`uv: command not found`** : relance `source ~/.bashrc` ou ouvre un nouveau terminal.
- **`/usr/bin/env: 'bash\r'`** ou erreurs bizarres dans le Makefile : fins de ligne Windows.
  Vérifie `git config core.autocrlf input` et n'édite pas les fichiers avec le Bloc-notes.
