import requests, time, json

HEADERS = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)'}

# Amazing Stories — détail par rightsCode ET enumcron pour voir les années
r = requests.get(
    'https://catalog.hathitrust.org/api/volumes/brief/issn/0002-7049.json',
    headers=HEADERS, timeout=15)
d = r.json()
items = d.get('items', [])

print(f'Amazing Stories — {len(items)} items total\n')
print('=== PD/PDUS ===')
for it in sorted(items, key=lambda x: x.get('enumcron','')):
    code = it.get('rightsCode','')
    cron = it.get('enumcron','')
    htid = it.get('htid','')
    if code in ('pd','pdus'):
        print(f'  {code:6s} | {cron:40s} | {htid}')

print('\n=== IC/ICUS ===')
for it in sorted(items, key=lambda x: x.get('enumcron','')):
    code = it.get('rightsCode','')
    cron = it.get('enumcron','')
    if code in ('ic','icus'):
        print(f'  {code:6s} | {cron:40s}')

# Même chose pour Weird Tales
time.sleep(0.5)
print('\n\n=== WEIRD TALES ===')
r2 = requests.get(
    'https://catalog.hathitrust.org/api/volumes/brief/issn/0043-1923.json',
    headers=HEADERS, timeout=15)
d2 = r2.json()
items2 = d2.get('items', [])
print(f'{len(items2)} items total')
for it in sorted(items2, key=lambda x: x.get('enumcron','')):
    code = it.get('rightsCode','')
    cron = it.get('enumcron','')
    if code in ('pd','pdus'):
        print(f'  {code:6s} | {cron}')
