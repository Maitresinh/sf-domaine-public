import mysql.connector, sqlite3

isf = mysql.connector.connect(host='mariadb-sfdb', port=3306,
    user='root', password='isfdb', database='isfdb')
ic = isf.cursor()

# Récupérer tous les title_ids short fiction magazines 1928-1963
ic.execute("""
    SELECT DISTINCT t.title_id
    FROM pubs p
    JOIN pub_content pc ON p.pub_id = pc.pub_id
    JOIN titles t ON pc.title_id = t.title_id
    WHERE p.pub_ctype = 'MAGAZINE'
    AND YEAR(p.pub_year) BETWEEN 1928 AND 1963
    AND t.title_ttype = 'SHORTFICTION'
""")
mag_ids = set(r[0] for r in ic.fetchall())
print(f'IDs magazines MariaDB: {len(mag_ids)}')
isf.close()

con = sqlite3.connect('/app/data/sf_dp.sqlite')
cur = con.cursor()
cur.execute('SELECT title_id FROM works WHERE "type"="shortfiction"')
sqlite_ids = set(r[0] for r in cur.fetchall())

overlap = mag_ids & sqlite_ids
print(f'Dans SQLite ET dans un magazine    : {len(overlap)}')
print(f'Dans SQLite SANS publication connue: {len(sqlite_ids - mag_ids)}')

# Parmi l'overlap, combien sont dp_us=NULL ?
if overlap:
    placeholders = ','.join('?' * len(overlap))
    cur.execute(f'''SELECT COUNT(*) FROM works 
        WHERE title_id IN ({placeholders}) AND dp_us IS NULL''',
        list(overlap))
    print(f'Overlap dp_us=NULL (cibles 14_): {cur.fetchone()[0]}')

    # Echantillon
    cur.execute(f'''SELECT title, author, year FROM works
        WHERE title_id IN ({placeholders}) AND dp_us IS NULL
        LIMIT 10''', list(overlap))
    print('\nEchantillon cibles :')
    for row in cur.fetchall():
        print(f'  [{row[2]}] {row[1]} — {row[0]}')
