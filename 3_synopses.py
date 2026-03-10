import sqlite_utils, requests, time

db = sqlite_utils.Database('/app/data/sf_dp.sqlite')

OLLAMA_URL = 'http://ollama:11434/api/generate'
OL_MODEL   = 'gemma3:latest'
OL_TIMEOUT = 60

def open_library(title, author):
    try:
        r = requests.get('https://openlibrary.org/search.json',
            params={'title': title, 'author': author, 'limit': 1}, timeout=10)
        docs = r.json().get('docs', [])
        if not docs:
            return None, None
        doc = docs[0]
        synopsis = doc.get('first_sentence', [None])[0] if doc.get('first_sentence') else None
        subjects = ', '.join(doc.get('subject', [])[:8]) or None
        return synopsis, subjects
    except Exception:
        return None, None

def ollama_synopsis(title, author, year):
    prompt = "In 3 sentences, describe the science fiction novel '" + title + "' by " + str(author) + " (" + str(year) + "). Be factual, no spoilers."
    try:
        r = requests.post(OLLAMA_URL,
            json={'model': OL_MODEL, 'prompt': prompt, 'stream': False},
            timeout=OL_TIMEOUT)
        return r.json().get('response', '').strip() or None
    except Exception as e:
        print('Ollama error: ' + str(e))
        return None

for col in ['synopsis', 'synopsis_source', 'subjects']:
    try:
        db.execute('ALTER TABLE works ADD COLUMN ' + col + ' TEXT')
    except Exception:
        pass

novels = list(db.execute("""
    SELECT title_id, title, author, year FROM works
    WHERE type='novel' AND has_french_vf=0 AND dp_eu=1
      AND (synopsis IS NULL OR synopsis='')
    ORDER BY award_count DESC, year ASC
""").fetchall())

print(str(len(novels)) + ' romans a traiter')
ok_ol, ok_ai, skipped = 0, 0, 0

for i, (title_id, title, author, year) in enumerate(novels):
    if i % 50 == 0:
        print(str(i) + '/' + str(len(novels)) + ' OL:' + str(ok_ol) + ' AI:' + str(ok_ai))
    synopsis, subjects, source = None, None, None
    synopsis, subjects = open_library(title, author)
    if synopsis:
        source = 'openlibrary'
        ok_ol += 1
    else:
        synopsis = ollama_synopsis(title, author, year)
        if synopsis:
            source = 'ollama'
            ok_ai += 1
        else:
            skipped += 1
    db['works'].update(title_id, {
        'synopsis': synopsis,
        'synopsis_source': source,
        'subjects': subjects,
    })
    time.sleep(0.1)

print('Termine — OL:' + str(ok_ol) + ' Ollama:' + str(ok_ai) + ' vides:' + str(skipped))
