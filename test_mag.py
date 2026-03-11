import mysql.connector, sqlite3, sys

try:
    isf = mysql.connector.connect(host='mariadb-sfdb', port=3306,
        user='root', password='isfdb', database='isfdb')
    ic = isf.cursor()
    print("MariaDB OK", flush=True)

    ic.execute("SELECT COUNT(*) FROM pub_content")
    print(f"pub_content total: {ic.fetchone()[0]}", flush=True)

    ic.execute("""
        SELECT COUNT(DISTINCT t.title_id)
        FROM pubs p
        JOIN pub_content pc ON p.pub_id = pc.pub_id
        JOIN titles t ON pc.title_id = t.title_id
        WHERE p.pub_ctype = 'MAGAZINE'
        AND YEAR(p.pub_year) BETWEEN 1928 AND 1963
        AND t.title_ttype = 'SHORTFICTION'
    """)
    print(f"Short fiction magazines 1928-1963: {ic.fetchone()[0]}", flush=True)
    isf.close()

except Exception as e:
    print(f"ERREUR: {e}", file=sys.stderr)
    sys.exit(1)

try:
    con = sqlite3.connect('/app/data/sf_dp.sqlite')
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM works WHERE "type"="shortfiction"')
    print(f"SQLite shortfiction total: {cur.fetchone()[0]}", flush=True)
except Exception as e:
    print(f"ERREUR SQLite: {e}", file=sys.stderr)
