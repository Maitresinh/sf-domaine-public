import requests, json, time

HEADERS = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)'}

# OCLCs des grands pulps SF — à valider
# Source : WorldCat / ISSN Portal
MAGAZINES = {
    'Weird Tales':                    '1642449',
    'Astounding Science Fiction':     '1480108',
    'Amazing Stories':                '1480085',
    'The Magazine of Fantasy and Science Fiction': '1554122',
    'Galaxy Science Fiction':         '1586123',
    'Thrilling Wonder Stories':       '1642455',
    'Fantastic Adventures':           '1480093',
}

for mag, oclc in MAGAZINES.items():
    try:
        r = requests.get(
            f'https://catalog.hathitrust.org/api/volumes/brief/oclc/{oclc}.json',
            headers=HEADERS, timeout=10)
        d = r.json()
        items = d.get('items', [])
        pd_items = [it for it in items if it.get('rightsCode') in ('pd','pdus')]
        ic_items = [it for it in items if it.get('rightsCode') in ('ic','icus')]
        print(f'{mag}')
        print(f'  OCLC {oclc} → {len(items)} items total, {len(pd_items)} pd/pdus, {len(ic_items)} ic/icus')
        if pd_items:
            print(f'  Exemple pd: {pd_items[0].get("htid")} | {pd_items[0].get("enumcron","")}')
        if not items:
            print(f'  ⚠️ OCLC incorrect — aucun item')
        time.sleep(0.5)
    except Exception as e:
        print(f'{mag} ERREUR: {e}')
