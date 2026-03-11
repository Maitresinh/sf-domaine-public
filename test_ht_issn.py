import requests, json, time

HEADERS = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)'}

# ISSNs des grands pulps SF — source : ISSN Portal / WorldCat
MAGAZINES_ISSN = {
    'Weird Tales':                     '0043-1923',
    'Astounding Science Fiction':      '0004-8658',
    'Amazing Stories':                 '0002-7049',
    'Galaxy Science Fiction':          '0016-4240',
    'The Magazine of Fantasy and SF':  '1046-1972',
    'Thrilling Wonder Stories':        '0040-7461',
    'Fantastic Adventures':            '0014-5610',
    'New Worlds SF':                   '0028-6079',
}

for mag, issn in MAGAZINES_ISSN.items():
    try:
        r = requests.get(
            f'https://catalog.hathitrust.org/api/volumes/brief/issn/{issn}.json',
            headers=HEADERS, timeout=10)
        d = r.json()
        items = d.get('items', [])
        pd_items  = [it for it in items if it.get('rightsCode') in ('pd','pdus')]
        ic_items  = [it for it in items if it.get('rightsCode') in ('ic','icus')]
        print(f'{mag} (ISSN {issn})')
        print(f'  {len(items)} items | {len(pd_items)} pd/pdus | {len(ic_items)} ic/icus')
        if pd_items:
            for it in pd_items[:3]:
                print(f'  ✅ {it.get("htid")} | {it.get("enumcron","")}')
        time.sleep(0.5)
    except Exception as e:
        print(f'  ERREUR: {e}')
