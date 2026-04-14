# Insta Downloader

Web app locale per scaricare foto e video da Instagram (solo profili pubblici).

## Installazione

```bash
# Clona il repo
git clone https://github.com/marrakechcurated/insta-downloader.git ~/insta-downloader

# Entra nella cartella
cd ~/insta-downloader

# Installa le dipendenze Python
pip3 install -r requirements.txt
```

## Avvio

```bash
cd ~/insta-downloader
python3 app.py
```

Apri **http://localhost:5000** nel browser.

## Come si usa

### Modalita 1 — Frontend web (singolo URL)
1. Apri `http://localhost:5000`
2. Incolla un URL Instagram (post, reel, carousel)
3. Clicca "Anteprima" per vedere cosa scaricherai
4. Clicca "Scarica tutto"
5. I file finiscono in `downloads/nome-utente/`

### Modalita 2 — Frontend web (batch)
1. Vai nel tab "Batch (piu URL)"
2. Incolla piu URL, uno per riga
3. Clicca "Scarica tutti"

### Modalita 3 — Da terminale (batch)
```bash
cd ~/insta-downloader
python3 batch.py https://www.instagram.com/p/ABC123/ https://www.instagram.com/reel/XYZ789/
```

### Modalita 4 — Claude Code scarica per te
Il redattore da a Claude Code una lista di link. Claude Code lancia:
```bash
cd ~/insta-downloader && python3 batch.py URL1 URL2 URL3
```

## Dove finiscono i file

```
downloads/
├── nome-utente-1/
│   ├── foto1.jpg
│   └── video1.mp4
└── nome-utente-2/
    └── foto2.jpg
```

Organizzati per username Instagram dell'autore del post.

## Problemi comuni

### "Errore 401" o "Login required"
Il profilo e privato. Questo tool funziona solo con profili pubblici.

### "Errore 429" o rallentamenti
Instagram limita le richieste. Aspetta qualche minuto e riprova.

### Instaloader non funziona piu
Instagram cambia spesso le API. Aggiorna:
```bash
pip3 install --upgrade instaloader
```

## Limiti
- Solo profili **pubblici**
- Instagram puo limitare le richieste se ne fai troppe in poco tempo
- I video Reels molto lunghi possono richiedere piu tempo
