# 🛠️ Stack Technique — SF Domaine Public

## 📦 Outils installés et validés

### Base de données
- **SQLite** (3.x) — Base principale (`sf_dp.sqlite`, ~500 Mo → 2-3 Go estimé après enrichissement)
- **MariaDB** (10.x) — Base ISFDB (2.8 Go, lecture seule)
- **sqlite-utils** (Python) — Manipulation SQLite avancée
- **ChromaDB** ⭐ — Vector database pour embeddings (SQLite-backed)

### Scraping & Web
- **Crawl4AI** (0.8.6) ⭐⭐⭐ — **PRIORITAIRE**
  - Scraping moderne avec anti-fingerprinting
  - Backend : Playwright
  - Usage : 22_, 24_, 27_ (Goodreads, Babelio)
  - **Avantages** : contourne blocages (500 errors), async, meilleur que BeautifulSoup
  - **Remplace** : Selenium + BeautifulSoup
- **Playwright** — Navigateur headless Chrome
  - Installation : `playwright install chromium`
  - Dépendances : libglib2.0-0, libnss3, libdrm2 (via `playwright install-deps`)
- **Selenium + Chrome** — Container dédié (legacy, à remplacer)
- **BeautifulSoup4** — Parsing HTML (fallback seulement)
- **Requests** — HTTP basique

### IA & Embeddings
- **Ollama** (container) ⭐⭐⭐ — **PRIORITAIRE**
  - Serveur LLM local, exploite RTX 3090
  - Port : 11434
  - **Avantages** : pas d'API payante, VRAM locale
  
**Modèles installés** :
- **bge-m3** ⭐⭐⭐ — **PRIORITAIRE**
  - Embeddings multilingues FR+EN
  - 1024 dimensions, 1.2 Go
  - Usage : 26_embeddings.py + agent découverte
  - **Remplace** : nomic-embed-text
- **gemma3:latest** — LLM génératif (agent éditorial)
- **qwen2.5-coder:14b** — Code generation

### Interface & Visualisation
- **Streamlit** ⭐⭐ — **PRIORITAIRE**
  - Container sf-dp-streamlit (port 8501)
  - GUI principale (`8_app.py`)
  - **Avantages** : prototypage ultra-rapide, pas de frontend séparé
- **Datasette** — Exploration SQL (port 8001)

### Python — Bibliothèques clés
```python
# Core
sqlite3, asyncio, json, logging, re, fcntl

# Web
requests, aiohttp
beautifulsoup4, lxml
crawl4ai ⭐
playwright ⭐

# IA
chromadb ⭐

# DB
mysql-connector-python
sqlite-utils

# Utils
unicodedata, datetime
```

### Infrastructure
- **Docker / Docker Compose** — Containers
- **Git + Git LFS** — Versioning + gros fichiers
- **Unraid NAS** — Hôte (RTX 3090, 62 Go RAM)

---

## 🎯 Stack recommandée pour prochains projets

### Top 5 — Must-have

#### 1. **Crawl4AI + Playwright** ⭐⭐⭐
```python
from crawl4ai import AsyncWebCrawler

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url, wait_for="css:.content")
```
**Use cases** : Tout scraping web, recherche, extraction données
**Avantages** : Anti-bot, async, meilleur taux succès

#### 2. **bge-m3 (Ollama)** ⭐⭐⭐
```python
import requests
r = requests.post('http://ollama:11434/api/embeddings',
    json={'model':'bge-m3','prompt':text})
embedding = r.json()['embedding']  # 1024 dimensions
```
**Use cases** : Recherche sémantique, RAG, clustering, similarité
**Avantages** : Multilingue FR+EN, local, pas d'API

#### 3. **ChromaDB** ⭐⭐⭐
```python
import chromadb
client = chromadb.PersistentClient(path="/data/chroma")
collection = client.create_collection("docs")
collection.add(embeddings=embeddings, documents=texts, ids=ids)
results = collection.query(query_embeddings=[query_emb], n_results=10)
```
**Use cases** : Vector DB, recherche similarité, RAG
**Avantages** : SQLite-backed, léger, pas de serveur séparé

#### 4. **Streamlit** ⭐⭐
```python
import streamlit as st
st.title("Mon App")
query = st.text_input("Recherche")
if st.button("Go"):
    results = search(query)
    st.write(results)
```
**Use cases** : Dashboards, démos, outils internes
**Avantages** : Prototypage ultra-rapide

#### 5. **Ollama (LLMs locaux)** ⭐⭐
```python
r = requests.post('http://ollama:11434/api/generate',
    json={'model':'gemma3:latest','prompt':prompt})
```
**Use cases** : Génération, agents, classification, résumés
**Avantages** : Local, pas de coût API, GPU exploité

---

## 🚫 À éviter / remplacer

| Outil ancien | Remplacer par | Raison |
|--------------|---------------|--------|
| Selenium | **Crawl4AI** | Plus rapide, anti-fingerprinting |
| BeautifulSoup seul | **Crawl4AI** | Bloqué par 500/403 errors |
| API payantes (OpenAI) | **Ollama local** | Coût, latence, confidentialité |
| Langchain | **ChromaDB + code** | Plus de contrôle, moins de dépendances |
| nomic-embed-text | **bge-m3** | Multilingue FR+EN |

---

## 💾 Gestion DB SQLite volumineuse

### Problème
- Taille actuelle : ~500 Mo
- Après enrichissement : **2-3 Go estimé**
- GitHub limite : 100 Mo/fichier, 1 Go/repo recommandé

### Solutions

#### 1. VACUUM + Compression GZIP ⭐ RECOMMANDÉ
```bash
# Optimiser (récupère espace)
docker exec sf-dp-tools python3 -c "
import sqlite3
c = sqlite3.connect('/app/data/sf_dp.sqlite')
c.execute('VACUUM')
c.close()
"

# Compresser
cd /mnt/user/sf-dp/data
gzip -9 -k sf_dp.sqlite  # Crée .gz

# Ratio : 70-80% compression
# 2 Go → 400-600 Mo
```

#### 2. Git LFS (fichiers > 100 Mo)
```bash
# Installer
git lfs install

# Tracker gros fichiers
git lfs track "data/*.sqlite"
git lfs track "data/*.sqlite.gz"

# Commit
git add .gitattributes
git add data/sf_dp.sqlite.gz
git commit -m "Backup DB compressée"
git push

# Limite : 1 Go gratuit/mois bandwidth
```

#### 3. Script backup automatique
```bash
#!/bin/bash
# /mnt/user/sf-dp/backup_db.sh
DATE=$(date +%Y-%m-%d)

# VACUUM
docker exec sf-dp-tools python3 -c "
import sqlite3
c = sqlite3.connect('/app/data/sf_dp.sqlite')
c.execute('VACUUM')
"

# Compress
gzip -9 -k /mnt/user/sf-dp/data/sf_dp.sqlite

# Backup local
cp data/sf_dp.sqlite.gz /mnt/user/backups/sf-dp/sf_dp_$DATE.sqlite.gz

# Git LFS si < 1 Go
SIZE=$(stat -c%s data/sf_dp.sqlite.gz)
if [ $SIZE -lt 1000000000 ]; then
    git add data/sf_dp.sqlite.gz
    git commit -m "Backup DB $DATE"
    git push
fi

# Nettoyer > 30 jours
find /mnt/user/backups/sf-dp/ -mtime +30 -delete
```

#### 4. Export JSON pour archives
```bash
# Export tables critiques
docker exec sf-dp-tools python3 -c "
import sqlite3, json, gzip
c = sqlite3.connect('/app/data/sf_dp.sqlite')
works = c.execute('SELECT * FROM works').fetchall()
cols = [d[0] for d in c.execute('PRAGMA table_info(works)').fetchall()]
data = [dict(zip([c[1] for c in cols], row)) for row in works]

with gzip.open('/app/data/works_export.json.gz', 'wt') as f:
    json.dump(data, f, ensure_ascii=False)
"
```

### Stratégie recommandée
1. **Backup local hebdomadaire** (script cron)
2. **Git LFS** pour versions majeures seulement
3. **Export JSON** pour archives long-terme
4. **Backup externe** (cloud/NAS) si > 1 Go

---

## 📋 Checklist nouveau projet

### Setup initial
```bash
# 1. Containers Docker
docker-compose up -d ollama chromadb

# 2. Installer Crawl4AI + Playwright
pip install crawl4ai
playwright install chromium
playwright install-deps chromium

# 3. Télécharger modèles Ollama
docker exec ollama ollama pull bge-m3
docker exec ollama ollama pull gemma3:latest

# 4. Tester stack
python3 test_stack.py
```

### Code template
```python
import asyncio
from crawl4ai import AsyncWebCrawler
import chromadb
import requests

# Scraping
async def scrape(url):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)
        return result.markdown

# Embeddings
def embed(text):
    r = requests.post('http://ollama:11434/api/embeddings',
        json={'model':'bge-m3','prompt':text})
    return r.json()['embedding']

# Vector DB
client = chromadb.PersistentClient(path="./chroma")
collection = client.get_or_create_collection("data")

# Pipeline
texts = asyncio.run(scrape("https://example.com"))
embeddings = [embed(t) for t in texts]
collection.add(embeddings=embeddings, documents=texts)
```

---

## 🎓 Leçons apprises

1. **Crawl4AI > Selenium** : Taux succès 95%+ vs 60% (500 errors contournés)
2. **bge-m3 > nomic-embed** : Support FR natif, meilleure qualité embeddings
3. **ChromaDB simple** : SQLite-backed = pas de serveur séparé, backup facile
4. **Ollama local** : RTX 3090 = gratuité + vitesse + confidentialité
5. **VACUUM régulier** : SQLite grossit vite, récupère 20-30% espace
6. **Git LFS tôt** : Ajouter dès que fichiers > 50 Mo, évite rewrite historique

---

## 🔗 Ressources

- Crawl4AI : https://github.com/unclecode/crawl4ai
- Ollama : https://ollama.com
- ChromaDB : https://www.trychroma.com
- bge-m3 : https://huggingface.co/BAAI/bge-m3
- Git LFS : https://git-lfs.github.com

---

**Dernière mise à jour** : 2026-04-06
**Projet** : SF Domaine Public
**Repo** : github.com/Maitresinh/sf-domaine-public
