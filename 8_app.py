import streamlit as st
import sqlite3, pandas as pd
DB = '/app/data/sf_dp.sqlite'
st.set_page_config(page_title='SF Domaine Public', layout='wide', page_icon='📚')
st.markdown("""
<style>
.tag  { background:#1e3a5f; color:#7eb8f7; padding:2px 8px;
        border-radius:10px; font-size:12px; margin:2px; display:inline-block; }
.dp   { background:#1a3a1a; color:#6fcf6f; padding:2px 8px;
        border-radius:10px; font-size:12px; margin:2px; display:inline-block; }
.award{ background:#3a2a00; color:#ffc947; padding:2px 8px;
        border-radius:10px; font-size:12px; margin:2px; display:inline-block; }
.list { background:#2a1a3a; color:#c47ef7; padding:2px 8px;
        border-radius:10px; font-size:12px; margin:2px; display:inline-block; }
.vf   { background:#1a2a3a; color:#7ecfcf; padding:2px 8px;
        border-radius:10px; font-size:12px; margin:2px; display:inline-block; }
.prio { background:#1a1a2a; color:#aaaaff; padding:2px 8px;
        border-radius:10px; font-size:12px; margin:2px; display:inline-block; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False, timeout=30)
def query(sql, params=()):
    return pd.read_sql_query(sql, get_conn(), params=params)
def run(sql, params=()):
    c = get_conn()
    c.execute(sql, params)
    c.commit()

def init_db():
    c = get_conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS editorial (
            title_id   INTEGER PRIMARY KEY,
            status     TEXT DEFAULT 'À évaluer',
            note       TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    for col, defn in [
        ('priority',    'INTEGER DEFAULT 3'),
        ('score',       'INTEGER DEFAULT 0'),
        ('groupe',      'TEXT'),
        ('tags_maison', 'TEXT'),
    ]:
        try:
            c.execute(f'ALTER TABLE editorial ADD COLUMN {col} {defn}')
        except Exception:
            pass
    c.commit()
init_db()

PRIORITY_LABELS = {1:'⚡ Urgente', 2:'🔴 Haute', 3:'🟡 Normale', 4:'🔵 Basse', 5:'⬜ Archive'}
PRIORITY_REV    = {v:k for k,v in PRIORITY_LABELS.items()}
ED_STATUTS      = ['À évaluer','Sélectionné','En cours','Rejeté']

@st.cache_data(ttl=3600)
def load_all_tags():
    df = query("SELECT isfdb_tags FROM works WHERE isfdb_tags IS NOT NULL")
    counts = {}
    for val in df['isfdb_tags']:
        for t in str(val).split(','):
            t = t.strip()
            if t: counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))

@st.cache_data(ttl=3600)
def load_award_names():
    df = query("SELECT awards FROM works WHERE awards IS NOT NULL AND awards != '' AND award_count > 0")
    counts = {}
    for val in df['awards']:
        if not val or str(val) in ('nan',''): continue
        for part in str(val).split('|'):
            part = part.strip()
            for emoji in ['🏆','🏅','📊']:
                if part.startswith(emoji):
                    rest = part[len(emoji):].strip()
                    name = rest.split('–')[0].split('#')[0].strip()
                    if name and len(name) > 3:
                        counts[name] = counts.get(name, 0) + 1
                    break
    return dict(sorted(counts.items(), key=lambda x: -x[1]))

for k, v in {
    'tags_include':[], 'tags_exclude':[], 'tags_mode':'ET',
    'series_filter':'',
    'award_levels':[], 'award_names':[],
    'selected':None, 'selected_author':None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

with st.sidebar:
    st.title('📚 SF Domaine Public')
    st.markdown('---')
    page = st.radio('Navigation', [
        '🔍 Catalogue','👤 Auteurs','📅 Prévisions DP',
        '📋 Sélection éditoriale','📊 Stats'
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CATALOGUE
# ═══════════════════════════════════════════════════════════════════════════════
# ── Fiche detail dialog ─────────────────────────────────────────────────────
@st.dialog("Fiche detail", width="large")
def show_fiche(r):
    title_q     = str(r.get("title",""))
    author_q    = str(r.get("author",""))
    title_slug  = title_q.replace(" ","+")
    author_slug = author_q.replace(" ","+")
    title_q     = str(r.get('title',''))
    author_q    = str(r.get('author',''))
    title_slug  = title_q.replace(' ','+')
    author_slug = author_q.replace(' ','+')

    with st.expander('📄 '+title_q, expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('**Auteur** : '+author_q)
            if r.get('birth_year') or r.get('death_year'):
                bio = str(r.get('birth_year') or '?')+' – '+str(r.get('death_year') or 'vivant')
                if r.get('birthplace'): bio += ' · '+str(r['birthplace'])
                st.caption('🗓 '+bio)
            st.markdown('**Année** : '+str(r['year']))
            st.markdown('**Type** : '+str(r.get('work_type',r.get('type','?'))))
            if r.get('series'):
                if st.button('📚 '+str(r['series']), key='series_detail', help='Filtrer par cette série'):
                    st.session_state.series_filter = str(r['series'])
                    st.session_state.selected = None; st.rerun()
            if r.get('langues_vf'):
                st.markdown('**Traduit en** : '+str(r['langues_vf']))

            if r.get('has_french_vf') == 1:
                vf_parts = []
                if r.get('first_vf_title'):  vf_parts.append('*'+str(r['first_vf_title'])+'*')
                elif r.get('last_vf_title'): vf_parts.append('*'+str(r['last_vf_title'])+'*')
                st.markdown('**🇫🇷 VF** : 🟢 ' + (' — '.join(vf_parts) if vf_parts else 'oui'))
                vf_cols = st.columns(3)
                vf_cols[0].metric('Première VF', r.get('first_vf_year') or '—')
                vf_cols[1].metric('Dernière VF', r.get('last_vf_year')  or '—')
                vf_cols[2].metric('Nb éditions FR', r.get('nb_vf_fr')   or '—')
                if r.get('last_vf_publisher'):
                    st.caption('🏢 Éditeur (dernière éd.) : '+str(r['last_vf_publisher']))
                if r.get('last_vf_translator'):
                    st.caption('✍️ Traducteur(s) : '+str(r['last_vf_translator']))
            else:
                st.markdown('**🇫🇷 VF** : 🔴 Non traduit en français')

        with c2:
            if r.get('annualviews'):    st.metric('Vues ISFDB/an', int(r['annualviews']))
            if r.get('fantlab_rating'): st.metric('FantLab', str(r['fantlab_rating'])+' ('+str(r.get('fantlab_votes','?'))+' votes)')
            if r.get('nb_reviews'):     st.metric('Critiques ISFDB', r['nb_reviews'])
            if r.get('rating'):         st.metric('Note ISFDB', r['rating'])

        # ── État du droit ────────────────────────────────────────────────
        st.markdown('---')
        st.markdown('### ⚖️ Analyse du droit')

        # Europe
        st.markdown('**🇪🇺 Droit européen (directive 2006/116/CE)**')
        if r.get('dp_eu') == 1:
            death = r.get('death_year') or '?'
            dp_eu_since = int(death) + 71 if isinstance(death, (int, float)) and death != '?' else '?'
            st.success(
                f"✅ Domaine public en Europe depuis le 1er janvier {dp_eu_since}. "
                f"L'auteur est décédé en {death} ; ses œuvres tombent dans le domaine public "
                "70 ans après sa mort (art. 1 de la directive européenne 2006/116/CE).")
        else:
            st.error("🔒 Protégé en Europe — l'auteur est décédé après 1955 ou la date de décès est inconnue.")

        # France
        st.markdown('**🇫🇷 Droit français (prorogation de guerre)**')
        if r.get('dp_fr') == 1:
            st.success(
                "✅ Domaine public en France. L'auteur est décédé avant 1948 : "
                "la prorogation de guerre française (+8 ans et 120 jours, art. L123-8 CPI) "
                "est épuisée, l'œuvre est libre de droits sur le territoire français.")
        elif r.get('dp_eu') == 1:
            death = r.get('death_year') or 0
            if death and int(death) >= 1948:
                st.warning(
                    f"⚠️ Domaine public EU mais prorogation de guerre à vérifier. "
                    f"L'auteur est décédé en {death}. Si ressortissant d'un pays "
                    "en guerre avec la France (Allemagne, Italie, Japon…), "
                    "une prorogation de +8 ans et 120 jours peut s'appliquer (art. L123-8 CPI).")
            else:
                st.info("ℹ️ Date de décès manquante — statut France non calculable.")
        else:
            st.error("🔒 Protégé en France (œuvre protégée en Europe).")

        # États-Unis
        st.markdown('**🇺🇸 Droit américain (Copyright Act)**')
        src    = r.get('dp_us_source') or ''
        reason = r.get('dp_us_reason') or ''
        year   = int(r.get('year') or 0)

        if r.get('dp_us') == 1:
            if not src and year < 1928:
                st.success(
                    f"✅ Domaine public aux États-Unis. Publication en {year}, "
                    "soit avant le 1er janvier 1928 : toutes les œuvres publiées "
                    "avant cette date sont automatiquement dans le domaine public américain, "
                    "sans condition de renouvellement (Copyright Act de 1976, §304).")
            elif src == 'cce_stanford_novel':
                st.success(
                    f"✅ Domaine public aux États-Unis. Roman publié en {year} "
                    "(période 1923–1963) : aucun renouvellement de copyright n'a été trouvé "
                    "dans le Catalogue of Copyright Entries (CCE) numérisé par Stanford. "
                    "Sous le Copyright Act de 1909, le copyright initial de 28 ans devait "
                    "être renouvelé auprès du Copyright Office ; faute de renouvellement, "
                    "l'œuvre est tombée dans le domaine public à l'expiration du premier terme.")
            elif src == 'cce_magazine_shortfiction':
                mag = r.get('mag_title') or 'magazine inconnu'
                mag_year = r.get('mag_year') or year
                st.success(
                    f"✅ Domaine public aux États-Unis. Nouvelle publiée en {mag_year} "
                    f"dans *{mag}*. Aucun renouvellement individuel n'a été trouvé dans le CCE "
                    "(Stanford) ni dans les contributions indexées par l'Online Books Page (UPenn). "
                    "La compilation du magazine n'a pas non plus été renouvelée pour la période "
                    "concernée. Sous le Copyright Act de 1909, faute de renouvellement dans les "
                    "28 ans, l'œuvre est tombée dans le domaine public.")
                if 'Convention de Berne' in reason:
                    st.info(
                        "📌 Convention de Berne : le non-renouvellement du copyright américain "
                        "(durée effective : 28 ans) est reconnu par les pays signataires. "
                        "L'œuvre est également considérée comme domaine public en Europe "
                        "par application de la règle du traitement national.")
            elif src == 'hathitrust':
                st.success(
                    "✅ Domaine public aux États-Unis, confirmé par HathiTrust Digital Library. "
                    "HathiTrust a vérifié le statut de droits de cette œuvre (code : pd) "
                    "et la met à disposition librement sur sa plateforme.")
            else:
                st.success(f"✅ Domaine public aux États-Unis (publication en {year}).")

        elif r.get('dp_us') == 0:
            if src == 'cce_upenn_magazine':
                st.error(
                    "🔒 Protégé aux États-Unis. Un renouvellement de copyright a été trouvé "
                    "dans le CCE (Stanford) ou dans les contributions indexées par UPenn "
                    "pour ce magazine. Le copyright a été renouvelé dans les délais légaux.")
            elif src == 'hathitrust':
                st.error("🔒 Protégé aux États-Unis, confirmé par HathiTrust Digital Library.")
            elif not src and year > 1963:
                st.error(
                    f"🔒 Protégé aux États-Unis. Publication en {year}, après 1963 : "
                    "sous le Copyright Act de 1976 et le Sonny Bono Act de 1998, "
                    "les œuvres publiées après 1963 sont protégées pendant 95 ans "
                    "à compter de la publication.")
            else:
                st.error("🔒 Protégé aux États-Unis.")
        else:
            if 1928 <= year <= 1963:
                st.warning(
                    f"❓ Statut américain non vérifié. Publication en {year} "
                    "(période 1923–1963) : une vérification dans le Catalogue of Copyright "
                    "Entries est nécessaire pour confirmer si le copyright a été renouvelé.")
            else:
                st.warning("❓ Statut américain non déterminé.")

        # Détail technique
        if reason or src:
            with st.expander('🔍 Détail technique'):
                st.caption(f"**Source de vérification :** {src or 'non renseignée'}")
                if reason: st.caption(f"**Motif enregistré :** {reason}")
                if r.get('mag_title'):
                    st.caption(f"**Magazine :** {r['mag_title']}"
                               + (f" ({r['mag_year']})" if r.get('mag_year') else ''))


        # ── Awards ───────────────────────────────────────────────────────
        if r.get('awards') and r.get('award_count') and int(r.get('award_count') or 0) > 0:
            st.markdown('**🏆 Awards**')
            for aw in str(r['awards']).split(' | '):
                if aw.strip(): st.markdown('- '+aw.strip())
        if r.get('isfdb_lists'):
            st.markdown('**Listes de référence** : '+str(r['isfdb_lists']))

        # Tags cliquables
        if r.get('isfdb_tags'):
            st.markdown('**Tags** — clic pour ajouter/retirer du filtre')
            tag_list = [t.strip() for t in str(r['isfdb_tags']).split(',') if t.strip()]
            t_cols = st.columns(min(len(tag_list),6))
            for ti, tag in enumerate(tag_list):
                active = tag in st.session_state.tags_include
                with t_cols[ti%6]:
                    lbl = ('✅ ' if active else '')+tag
                    if st.button(lbl, key=f'ftag_{r["title_id"]}_{ti}'):
                        if active:
                            st.session_state.tags_include = [t for t in st.session_state.tags_include if t!=tag]
                        else:
                            st.session_state.tags_include = st.session_state.tags_include+[tag]
                        st.session_state.selected = None; st.rerun()

        if r.get('synopsis'):
            st.markdown('**Synopsis** (ISFDB)'); st.info(str(r['synopsis']))

        # ── Critiques & Évaluations ───────────────────────────────────────
        st.markdown('---')
        st.markdown('**📊 Critiques & Évaluations**')
        cr1,cr2,cr3,cr4,cr5 = st.columns(5)
        cr1.metric('Note ISFDB',   r.get('rating')         or '—')
        cr2.metric('Goodreads',    r.get('gr_rating')      or '—')
        cr3.metric('FantLab',      r.get('fantlab_rating') or '—')
        cr4.metric('Open Library', r.get('ol_rating')      or '—')
        cr5.metric('Vues/an',      int(r['annualviews']) if r.get('annualviews') else '—')

        # Snippets Goodreads
        if r.get('gr_reviews_text'):
            import json as _json
            try:
                snippets = _json.loads(r['gr_reviews_text'])
                if snippets and len(snippets) > 0:
                    with st.expander(f'💬 Extraits Goodreads ({len(snippets)} avis)'):
                        for s in snippets[:5]:
                            if str(s).strip():
                                st.markdown('> '+str(s)[:300])
                                st.markdown('---')
            except Exception:
                if str(r['gr_reviews_text']).strip():
                    st.caption(str(r['gr_reviews_text'])[:200])

        # Critiques noosfere.org
        noo_critiques = get_conn().execute("""
            SELECT nt.chroniqueur, nt.texte
            FROM noosfere_textes nt
            JOIN noosfere_critiques nc ON nc.numlivre = nt.numlivre
            WHERE nc.title_id = ? AND nt.texte IS NOT NULL AND nt.is_serie = 0
            ORDER BY nt.id
        """, (r['title_id'],)).fetchall()
        if noo_critiques:
            with st.expander(f'📰 Critiques noosfere.org ({len(noo_critiques)})'):
                for crit in noo_critiques:
                    if crit[0]:
                        st.markdown(f'**{crit[0]}**')
                    st.markdown(str(crit[1])[:1500]+(' …' if len(str(crit[1]))>1500 else ''))
                    st.markdown('---')

        # Description Open Library
        if r.get('ol_description'):
            with st.expander('📖 Description Open Library'):
                st.info(str(r['ol_description'])[:600])

        # Liens critiques
        links_crit = []
        noo_num = get_conn().execute(
            "SELECT numlivre FROM noosfere_critiques WHERE title_id=? LIMIT 1",
            (r['title_id'],)).fetchone()
        if noo_num:
            links_crit.append('[noosfere.org](https://www.noosfere.org/livres/niourf.asp?numlivre='+str(noo_num[0])+')')
        if r.get('nb_reviews') and int(r['nb_reviews'])>0:
            links_crit.append('[Critiques ISFDB](https://www.isfdb.org/cgi-bin/title.cgi?'+str(r['title_id'])+'#reviews)')
        if r.get('goodreads_id'):
            links_crit.append('[Goodreads](https://www.goodreads.com/book/show/'+str(r['goodreads_id'])+')')
        if r.get('fantlab_url'):
            links_crit.append('[FantLab]('+str(r['fantlab_url'])+')')
        else:
            links_crit.append('[FantLab 🔍](https://fantlab.ru/search?q='+title_slug+')')
        links_crit.append('[LibraryThing](https://www.librarything.com/search.php?term='+title_slug+'&searchthing=work)')
        if links_crit: st.markdown('  ·  '.join(links_crit))

        # ── Éditions ─────────────────────────────────────────────────────
        st.markdown('---'); st.markdown('**📚 Éditions**')
        ed1, ed2 = st.columns(2)
        ed1.metric('Nb éditions toutes langues', r.get('nb_editions')    or '—')
        ed2.metric('1ère publication',           r.get('first_pub_year') or '—')

        # ── Chargement enrichi ────────────────────────────────────────────
        st.markdown('---')
        load_key = 'loaded_'+str(r['title_id'])
        if load_key not in st.session_state: st.session_state[load_key] = None

        if st.button('🔄 Charger bio, éditions, critiques', key='load_'+str(r['title_id'])):
            import requests as req
            loaded = {}
            try:
                wp = req.get('https://en.wikipedia.org/api/rest_v1/page/summary/'+author_q.replace(' ','_'), timeout=6)
                if wp.status_code==200:
                    wpd = wp.json()
                    if wpd.get('extract') and len(wpd['extract'])>100:
                        loaded['author_bio']    = wpd.get('extract','')[:800]
                        loaded['author_desc']   = wpd.get('description','')
                        loaded['author_thumb']  = wpd.get('thumbnail',{}).get('source')
                        loaded['author_wp_url'] = wpd.get('content_urls',{}).get('desktop',{}).get('page','')
            except Exception: pass

            if r.get('translator'):
                trans_bios = []
                for chunk in str(r['translator']).split(';'):
                    name = chunk.split('(')[0].strip()
                    if not name: continue
                    for lang in ['en','fr']:
                        try:
                            wpt = req.get(f'https://{lang}.wikipedia.org/api/rest_v1/page/summary/'+name.replace(' ','_'), timeout=5)
                            if wpt.status_code==200:
                                td = wpt.json()
                                if td.get('extract') and len(td['extract'])>50:
                                    trans_bios.append({'name':name,'desc':td.get('description',''),'extract':td['extract'][:300]})
                                    break
                        except Exception: pass
                loaded['trans_bios'] = trans_bios

            if not r.get('synopsis'):
                for slug in [title_q.replace(' ','_'),
                             title_q.replace(' ','_')+'_('+author_q.split()[-1]+'_novel)',
                             title_q.replace(' ','_')+'_(novel)']:
                    try:
                        wps = req.get('https://en.wikipedia.org/api/rest_v1/page/summary/'+slug, timeout=6)
                        if wps.status_code==200:
                            wpsd = wps.json()
                            ex = wpsd.get('extract','')
                            if ex and len(ex)>100 and wpsd.get('type')=='standard':
                                loaded['wp_synopsis']     = ex[:800]
                                loaded['wp_synopsis_url'] = wpsd.get('content_urls',{}).get('desktop',{}).get('page','')
                                break
                    except Exception: pass

            try:
                ol = req.get('https://openlibrary.org/search.json',
                             params={'title':title_q,'author':author_q,'limit':1}, timeout=8)
                docs = ol.json().get('docs',[])
                if docs:
                    d = docs[0]
                    loaded['ol'] = {
                        'editions':   d.get('edition_count','?'),
                        'first_year': d.get('first_publish_year','?'),
                        'rating':     str(round(d['ratings_average'],1)) if d.get('ratings_average') else '—',
                        'votes':      d.get('ratings_count','—'),
                        'subjects':   ', '.join(d.get('subject',[])[:12]),
                        'url':        'https://openlibrary.org'+d.get('key',''),
                    }
            except Exception: pass

            st.session_state[load_key] = loaded

        if st.session_state.get(load_key):
            loaded = st.session_state[load_key]
            if loaded.get('author_bio'):
                st.markdown('### 👤 '+author_q)
                cb1,cb2 = st.columns([3,1])
                with cb1:
                    st.info(loaded['author_bio']); st.caption(loaded.get('author_desc',''))
                    wp_url = loaded.get('author_wp_url','')
                    if wp_url:
                        st.markdown('[Wikipedia EN]('+wp_url+')  ·  [Wikipedia FR]('+wp_url.replace('en.wikipedia.org','fr.wikipedia.org')+')')
                with cb2:
                    if loaded.get('author_thumb'): st.image(loaded['author_thumb'], width=120)

            if loaded.get('trans_bios'):
                st.markdown('### 🖊️ Traducteur(s)')
                for tb in loaded['trans_bios']:
                    st.markdown('**'+tb['name']+'** — '+tb['desc']); st.caption(tb['extract'])

            if loaded.get('wp_synopsis'):
                st.markdown('### 📖 Synopsis (Wikipedia)'); st.info(loaded['wp_synopsis'])
                if loaded.get('wp_synopsis_url'):
                    st.markdown('[→ Article Wikipedia]('+loaded['wp_synopsis_url']+')')

            if loaded.get('ol'):
                ol = loaded['ol']; st.markdown('### 📚 Open Library')
                o1,o2,o3,o4 = st.columns(4)
                o1.metric('Éditions',ol['editions']); o2.metric('1ère éd.',ol['first_year'])
                o3.metric('Note OL',ol['rating']);    o4.metric('Votes OL',ol['votes'])
                if ol['subjects']: st.caption('Sujets : '+ol['subjects'])
                st.markdown('[→ Open Library]('+ol['url']+')')

        # ── Liens ─────────────────────────────────────────────────────────
        st.markdown('---'); st.markdown('**🔗 Liens**')
        lc1,lc2,lc3 = st.columns(3)
        with lc1:
            st.markdown('**Sources**')
            st.markdown('🔹 [ISFDB titre](https://www.isfdb.org/cgi-bin/title.cgi?'+str(r['title_id'])+')')
            st.markdown('🔹 [ISFDB auteur](https://www.isfdb.org/cgi-bin/ea.cgi?'+author_slug+')')
            if r.get('wikipedia_url'):
                st.markdown('🔹 [Wikipedia EN]('+str(r['wikipedia_url'])+')')
                st.markdown('🔹 [Wikipedia FR]('+str(r['wikipedia_url']).replace('en.wikipedia.org','fr.wikipedia.org')+')')
        with lc2:
            st.markdown('**Avis lecteurs**')
            if r.get('goodreads_id'):
                gid = str(r['goodreads_id'])
                st.markdown('🔹 [Goodreads](https://www.goodreads.com/book/show/'+gid+')')
                st.markdown('🔹 [Goodreads critiques](https://www.goodreads.com/book/reviews/'+gid+')')
            st.markdown('🔹 [Open Library](https://openlibrary.org/search?title='+title_slug+'&author='+author_slug+')')
            st.markdown('🔹 [FantLab 🇷🇺](https://fantlab.ru/search?q='+title_slug+')')
            st.markdown('🔹 [LibraryThing](https://www.librarything.com/search.php?term='+title_slug+'&searchthing=work)')
        with lc3:
            st.markdown('**Texte en ligne**')
            st.markdown('🔹 [Project Gutenberg](https://www.gutenberg.org/ebooks/search/?query='+title_slug+'+'+author_slug+')')
            st.markdown('🔹 [Internet Archive](https://archive.org/search?query='+title_slug+'+'+author_slug+')')
            st.markdown('🔹 [Standard Ebooks](https://standardebooks.org/ebooks?query='+title_slug+')')
            if r.get('goodreads_id'):
                st.markdown('🔹 [WorldCat](https://www.worldcat.org/search?q='+title_slug+'+'+author_slug+')')

        # ── Note éditoriale ───────────────────────────────────────────────
        st.markdown('---')
        ex = query('SELECT note FROM editorial WHERE title_id=?', (int(r['title_id']),))
        cur_note = ex.iloc[0]['note'] if len(ex)>0 and ex.iloc[0]['note'] else ''
        note = st.text_area('Note éditoriale', value=cur_note, key='n_'+str(r['title_id']))
        if st.button('Sauvegarder'):
            run("""INSERT INTO editorial (title_id,note,updated_at) VALUES(?,?,datetime('now'))
                   ON CONFLICT(title_id) DO UPDATE SET note=excluded.note,updated_at=excluded.updated_at""",
                (int(r['title_id']),note))
            st.success('✅ Sauvegardé')
        if st.button('🚀 Envoyer à Turjman'):
            st.info('POST /jobs — title_id='+str(r['title_id'])+' · '+title_q+' · '+author_q)

    # ═══════════════════════════════════════════════════════════════════════════════
    # PAGE AUTEURS
    # ═══════════════════════════════════════════════════════════════════════════════


if page == '🔍 Catalogue':
    with st.sidebar:
        st.subheader('Filtres')
        author_search = st.text_input('Auteur', placeholder='ex: Asimov')
        title_search  = st.text_input('Titre',  placeholder='ex: Foundation')

        series_search = st.text_input('📚 Série',
            value=st.session_state.series_filter,
            placeholder='ex: Lensman, Conan…', key='series_input')
        if series_search != st.session_state.series_filter:
            st.session_state.series_filter = series_search
        if st.session_state.series_filter:
            if st.button('✕ Effacer série'): st.session_state.series_filter = ''; st.rerun()

        tag_counts  = load_all_tags()
        tag_options = [f"{t} ({n})" for t,n in tag_counts.items()]
        tag_labels  = list(tag_counts.keys())
        def tag2opt(t): return f"{t} ({tag_counts[t]})" if t in tag_counts else t

        st.markdown('**🏷 Tags**')
        tags_mode = st.radio('Mode inclusion', ['ET','OU'], horizontal=True,
                             index=0 if st.session_state.tags_mode=='ET' else 1)
        st.session_state.tags_mode = tags_mode
        inc_sel = st.multiselect('Inclure', tag_options,
                                  default=[tag2opt(t) for t in st.session_state.tags_include if t in tag_counts],
                                  key='tags_inc')
        exc_sel = st.multiselect('Exclure', tag_options,
                                  default=[tag2opt(t) for t in st.session_state.tags_exclude if t in tag_counts],
                                  key='tags_exc')
        st.session_state.tags_include = [tag_labels[tag_options.index(x)] for x in inc_sel if x in tag_options]
        st.session_state.tags_exclude = [tag_labels[tag_options.index(x)] for x in exc_sel if x in tag_options]

        aw_counts  = load_award_names()
        aw_options = [f"{n} ({c})" for n,c in aw_counts.items()]
        aw_labels  = list(aw_counts.keys())
        def aw2opt(n): return f"{n} ({aw_counts[n]})" if n in aw_counts else n

        st.markdown('**🏆 Awards**')
        aw_levels = st.multiselect('Niveau',
                                    ['🏆 Victoire','🏅 Nomination','📊 Sondage'],
                                    default=st.session_state.award_levels, key='aw_levels')
        st.session_state.award_levels = aw_levels
        aw_names = st.multiselect('Prix', aw_options,
                                   default=[aw2opt(n) for n in st.session_state.award_names if n in aw_counts],
                                   key='aw_names_sel')
        st.session_state.award_names = [aw_labels[aw_options.index(x)] for x in aw_names if x in aw_options]

        types = st.multiselect('Type',
            ['novel','novella','novelette','short story','shortfiction','collection','anthology','omnibus'],
            default=['novel'])
        c1c, c2c = st.columns(2)
        with c1c: year_min = st.number_input('Année min', 1850, 2000, 1900)
        with c2c: year_max = st.number_input('Année max', 1850, 2030, 1963)

        dp_filter = st.selectbox('Domaine public', [
            'DP EU (mort avant 1956)','DP US confirmé (CCE)','DP EU + US confirmé',
            'DP US OU EU','Hors DP (protégé)','Tous statuts'])
        vf_filter = st.selectbox('Traduction française',
            ['Sans VF (à traduire)','Avec VF (déjà traduit)','Toutes'])
        synopsis_only = st.checkbox('Avec synopsis')
        lists_only    = st.checkbox('Dans une liste de référence')
        lang_filter   = st.selectbox('Traduit ailleurs', [
            'Toutes','Traduit ailleurs (≥1 langue)','Traduit ailleurs (≥3 langues)','Aucune traduction'])
        _con = get_conn()
        _lang_rows = _con.execute("""
            SELECT lang_orig, COUNT(*) n FROM works
            WHERE lang_orig IS NOT NULL
            GROUP BY lang_orig ORDER BY n DESC
            """).fetchall()
        _lang_opts = ['English (défaut) ('+str(_con.execute('SELECT COUNT(*) FROM works WHERE lang_orig IS NULL').fetchone()[0])+')']
        _lang_opts += [r[0]+' ('+str(r[1])+')' for r in _lang_rows]
        _lang_sel = st.multiselect('Langue originale', _lang_opts)
        lang_orig_filter = []
        for x in _lang_sel:
            lang_orig_filter.append(x.rsplit(' (',1)[0])
        sort_by = st.selectbox('Trier par', [
            'annualviews DESC','award_count DESC','year ASC','year DESC',
            'fantlab_rating DESC','nb_reviews DESC'])
        limit = st.slider('Résultats max', 20, 2000, 100)

    # ── SQL ───────────────────────────────────────────────────────────────────
    where, params = ['1=1'], []
    if types:
        where.append('UPPER(w."type") IN (' + ','.join(['?']*len(types)) + ')')
        params.extend([t.upper() for t in types])
    where.append('w.year >= ? AND w.year <= ?')
    params.extend([year_min, year_max])

    dp_map = {
        'DP EU (mort avant 1956)': 'w.dp_eu = 1',
        'DP US confirmé (CCE)':    'w.dp_us = 1',
        'DP EU + US confirmé':     'w.dp_eu = 1 AND w.dp_us = 1',
        'DP US OU EU':             '(w.dp_eu = 1 OR w.dp_us = 1)',
        'Hors DP (protégé)':       'w.dp_eu = 0 AND (w.dp_us = 0 OR w.dp_us IS NULL)',
    }
    if dp_filter in dp_map: where.append(dp_map[dp_filter])
    if vf_filter == 'Sans VF (à traduire)':    where.append('w.has_french_vf = 0')
    elif vf_filter == 'Avec VF (déjà traduit)': where.append('w.has_french_vf = 1')
    if author_search: where.append('w.author LIKE ?'); params.append('%'+author_search+'%')
    if lang_orig_filter:
        clauses = []
        for lang in lang_orig_filter:
            if lang == 'English (défaut)':
                clauses.append('w.lang_orig IS NULL')
            else:
                clauses.append('w.lang_orig = ?')
                params.append(lang)
        where.append('(' + ' OR '.join(clauses) + ')')
    if title_search:  where.append('w.title  LIKE ?'); params.append('%'+title_search+'%')
    if st.session_state.series_filter:
        where.append('w.series LIKE ?'); params.append('%'+st.session_state.series_filter+'%')
    if synopsis_only: where.append('w.synopsis IS NOT NULL')
    if lists_only:    where.append('w.isfdb_lists IS NOT NULL')
    if lang_filter == 'Traduit ailleurs (≥1 langue)':    where.append('w.nb_langues_vf >= 1')
    elif lang_filter == 'Traduit ailleurs (≥3 langues)': where.append('w.nb_langues_vf >= 3')
    elif lang_filter == 'Aucune traduction':              where.append('w.nb_langues_vf = 0')
    if st.session_state.tags_include:
        if st.session_state.tags_mode == 'ET':
            for t in st.session_state.tags_include:
                where.append('w.isfdb_tags LIKE ?'); params.append('%'+t+'%')
        else:
            or_p = ' OR '.join(['w.isfdb_tags LIKE ?']*len(st.session_state.tags_include))
            where.append('('+or_p+')')
            params.extend(['%'+t+'%' for t in st.session_state.tags_include])
    for t in st.session_state.tags_exclude:
        where.append('(w.isfdb_tags NOT LIKE ? OR w.isfdb_tags IS NULL)')
        params.append('%'+t+'%')
    if st.session_state.award_levels:
        lvl_map = {'🏆 Victoire':'🏆','🏅 Nomination':'🏅','📊 Sondage':'📊'}
        or_p = ' OR '.join(['w.awards LIKE ?']*len(st.session_state.award_levels))
        where.append('('+or_p+')')
        params.extend(['%'+lvl_map[l]+'%' for l in st.session_state.award_levels])
    if st.session_state.award_names:
        or_p = ' OR '.join(['w.awards LIKE ?']*len(st.session_state.award_names))
        where.append('('+or_p+')')
        params.extend(['%'+n+'%' for n in st.session_state.award_names])

    sql = """
        SELECT w.title_id, w.title, w.author, w.year,
               w."type" as work_type,
               w.has_french_vf, w.french_title,
               w.dp_eu, w.dp_us, w.dp_us_reason, w.dp_us_source,
               w.dp_fr, w.mag_title, w.mag_year,
               w.award_count, w.awards, w.award_score,
               w.annualviews, w.rating,
               w.fantlab_rating, w.fantlab_votes, w.nb_reviews,
               w.gr_rating, w.gr_reviews_text,
               w.ol_rating, w.ol_description,
               w.isfdb_tags, w.isfdb_lists, w.synopsis,
               w.nb_langues_vf, w.langues_vf, w.series,
               w.wikipedia_url, w.goodreads_id, w.translator,
               w.birth_year, w.death_year, w.birthplace,
               w.nb_editions, w.first_pub_year,
               w.last_vf_year, w.last_vf_publisher, w.last_vf_title,
               w.first_vf_year, w.first_vf_title, w.last_vf_translator, w.nb_vf_fr,
               w.lang_orig,
               COALESCE(e.status,'À évaluer') as status
        FROM works w
        LEFT JOIN editorial e ON w.title_id = e.title_id
        WHERE """ + ' AND '.join(where) + """
        ORDER BY w.""" + sort_by + " LIMIT ?"

    params.append(limit)
    df = query(sql, params)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric('Résultats', len(df))
    c2.metric('Sans VF',   int((df['has_french_vf']==0).sum()))
    c3.metric('Avec VF',   int((df['has_french_vf']==1).sum()))
    c4.metric('Primés',    int((df['award_count'].fillna(0).astype(int)>0).sum()))
    c5.metric('Avec synopsis', int(df['synopsis'].notna().sum()))
    st.markdown('---')

    for _, row in df.iterrows():
        with st.container():
            col_main, col_status = st.columns([5,1])
            with col_main:
                vf_icon = '🟢' if row['has_french_vf']==1 else '🔴'
                year_s  = str(int(row['year'])) if row['year'] else '?'
                st.markdown(vf_icon+' **'+str(row['title'])+'**  ·  '
                            +str(row['author'])+'  ·  '+year_s
                            +'  ·  *'+str(row.get('work_type','?'))+'*')
                badges = ''
                if row['dp_eu']==1 and row['dp_us']==1:  badges += '<span class="dp">✅ DP EU+US</span> '
                elif row['dp_eu']==1:                     badges += '<span class="dp">🇪🇺 DP EU</span> '
                elif row['dp_us']==1:                     badges += '<span class="dp">🇺🇸 DP US</span> '
                if row.get('dp_fr')==1:                   badges += '<span class="dp">🇫🇷 DP FR</span> '
                if row['has_french_vf']==1 and row['french_title']:
                    badges += '<span class="vf">🇫🇷 '+str(row['french_title'])[:40]+'</span> '
                if row['award_count'] and int(row['award_count'])>0 and row.get('awards'):
                    badges += '<span class="award">🏆 '+str(int(row['award_count']))+' award(s)</span> '
                if row['isfdb_lists']: badges += '<span class="list">📋 Liste ref.</span> '
                if row['series']:      badges += '<span class="tag">📚 '+str(row['series'])[:30]+'</span> '
                if row['isfdb_tags']:
                    for t in str(row['isfdb_tags']).split(',')[:5]:
                        if t.strip(): badges += '<span class="tag">'+t.strip()+'</span> '
                if badges: st.markdown(badges, unsafe_allow_html=True)

                ratings = []
                if row['annualviews']:                               ratings.append('👁 '+str(int(row['annualviews']))+'/an')
                if row.get('gr_rating'):                             ratings.append('GR ⭐'+str(row['gr_rating']))
                if row.get('fantlab_rating'):                        ratings.append('FL ⭐'+str(row['fantlab_rating']))
                if row['nb_reviews']:                                ratings.append('💬 '+str(row['nb_reviews'])+' critiques')
                if row['nb_langues_vf'] and int(row['nb_langues_vf'])>0: ratings.append('🌍 '+str(int(row['nb_langues_vf']))+' langues')
                if ratings: st.caption('  ·  '.join(ratings))
                if row['synopsis']:
                    st.caption('📖 '+str(row['synopsis'])[:250]+('…' if len(str(row['synopsis']))>250 else ''))

            with col_status:
                cur = row['status'] if row['status'] in ED_STATUTS else 'À évaluer'
                new = st.selectbox('Statut', ED_STATUTS, index=ED_STATUTS.index(cur), key='s_'+str(row['title_id']))
                if new != cur:
                    run("""INSERT INTO editorial (title_id,status,updated_at) VALUES(?,?,datetime('now'))
                           ON CONFLICT(title_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at""",
                        (int(row['title_id']),new))
                    st.rerun()
                if st.button('Détail', key='b_'+str(row['title_id'])):
                    st.session_state.selected = row.to_dict()
        st.divider()

    # ── Fiche détail ──────────────────────────────────────────────────────────
    if st.session_state.selected:
        show_fiche(st.session_state.selected)
elif page == '👤 Auteurs':
    with st.sidebar:
        st.subheader('Filtres auteurs')
        letter    = st.selectbox('Lettre', ['Tous']+list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        dp_auth   = st.selectbox('DP', ['DP EU ou US','DP EU','DP US confirmé','Toute la bibliographie'])
        vf_auth   = st.selectbox('Traduction FR', ['Tous','Au moins une œuvre sans VF','Tout traduit'])
        min_works = st.slider('Nb œuvres minimum', 1, 20, 1)
        sort_auth = st.selectbox('Trier par', ['nb_sans_vf DESC','nb_total DESC','nb_primés DESC','author ASC'])

    where_a, params_a = [], []
    if dp_auth=='DP EU':              where_a.append('dp_eu = 1')
    elif dp_auth=='DP US confirmé':   where_a.append('dp_us = 1')
    elif dp_auth!='Toute la bibliographie': where_a.append('(dp_eu=1 OR dp_us=1)')
    if letter!='Tous': where_a.append('author LIKE ?'); params_a.append(letter+'%')
    cond = ' AND '.join(where_a) if where_a else '1=1'

    df_auth = query("""
        SELECT author,
               COUNT(*) as nb_total,
               SUM(CASE WHEN has_french_vf=0 THEN 1 ELSE 0 END) as nb_sans_vf,
               SUM(CASE WHEN has_french_vf=1 THEN 1 ELSE 0 END) as nb_avec_vf,
               SUM(CASE WHEN award_count>0 THEN 1 ELSE 0 END) as nb_primés,
               SUM(CASE WHEN "type"='novel' AND has_french_vf=0 THEN 1 ELSE 0 END) as romans_sans_vf,
               MAX(annualviews) as max_views, MIN(year) as debut, MAX(year) as fin
        FROM works WHERE """+cond+"""
        GROUP BY author HAVING nb_total >= ? """+
        ("AND nb_sans_vf > 0" if vf_auth=='Au moins une œuvre sans VF'
         else "AND nb_sans_vf = 0" if vf_auth=='Tout traduit' else "")+"""
        ORDER BY """+sort_auth+""" LIMIT 300""",
        params_a+[min_works])

    st.title('👤 Auteurs — '+str(len(df_auth))+' trouvés')
    for _, row in df_auth.iterrows():
        ca, cb, cc = st.columns([3,4,1])
        with ca:
            st.markdown('**'+str(row['author'])+'**')
            st.caption(str(int(row['debut']))+' – '+str(int(row['fin'])))
        with cb:
            badges = '<span class="dp">'+str(int(row['nb_sans_vf']))+' sans VF</span> '
            if row['nb_avec_vf']>0:     badges += '<span class="vf">'+str(int(row['nb_avec_vf']))+' avec VF</span> '
            if row['nb_primés']>0:      badges += '<span class="award">🏆 '+str(int(row['nb_primés']))+' primés</span> '
            if row['romans_sans_vf']>0: badges += '<span class="tag">📖 '+str(int(row['romans_sans_vf']))+' romans</span> '
            if row['max_views']:        badges += '<span class="tag">👁 '+str(int(row['max_views']))+'</span> '
            st.markdown(badges, unsafe_allow_html=True)
        with cc:
            if st.button('Œuvres', key='auth_'+str(row['author'])):
                st.session_state.selected_author = row['author']

    if st.session_state.selected_author:
        auth = st.session_state.selected_author
        st.markdown('---'); st.subheader('📚 '+auth)
        df_oeuvres = query("""
            SELECT title, year, "type" as work_type, has_french_vf, french_title,
                   dp_eu, dp_us, dp_us_reason, award_count, awards,
                   synopsis, annualviews, nb_langues_vf, langues_vf, isfdb_tags
            FROM works WHERE author=? ORDER BY has_french_vf ASC, "type", year""", (auth,))
        for _, r in df_oeuvres.iterrows():
            vf_icon  = '🟢' if r['has_french_vf']==1 else '🔴'
            year_s   = str(int(r['year'])) if r['year'] else '?'
            dp_badge = (' ✅' if r['dp_eu']==1 and r['dp_us']==1 else
                        ' 🇪🇺' if r['dp_eu']==1 else ' 🇺🇸' if r['dp_us']==1 else ' 🔒')
            line = vf_icon+dp_badge+' **'+str(r['title'])+'** ('+year_s+') — *'+str(r.get('work_type','?'))+'*'
            if r['has_french_vf']==1 and r['french_title']: line += ' → 🇫🇷 '+str(r['french_title'])
            if r['award_count'] and r['award_count']>0 and r.get('awards'): line += ' 🏆'
            st.markdown(line)
            if r['synopsis']: st.caption('📖 '+str(r['synopsis'])[:180]+'…')

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE PRÉVISIONS DP
# ═══════════════════════════════════════════════════════════════════════════════
elif page == '📅 Prévisions DP':
    st.title('📅 Prévisions d\'entrée dans le domaine public')
    st.caption('Règle EU : auteur mort en année X → DP le 1er janvier X+71')

    with st.sidebar:
        st.subheader('Filtres prévisions')
        year_range  = st.slider('Années à venir', 2026, 2040, (2026,2032))
        prev_types  = st.multiselect('Type', ['novel','novella','novelette','short story','shortfiction','collection'],
                                     default=['novel'])
        prev_vf     = st.selectbox('Traduction FR', ['Sans VF','Avec VF','Toutes'])
        prev_awards = st.checkbox('Primés / cités uniquement')

    y_min, y_max = year_range
    where_p  = ['death_year BETWEEN ? AND ?','death_year IS NOT NULL','dp_eu=0','dp_us=0']
    params_p = [y_min-71, y_max-71]
    if prev_types:
        where_p.append('"type" IN ('+','.join(['?']*len(prev_types))+')')
        params_p.extend(prev_types)
    if prev_vf=='Sans VF':   where_p.append('has_french_vf=0')
    elif prev_vf=='Avec VF': where_p.append('has_french_vf=1')
    if prev_awards: where_p.append('(award_count>0 OR award_score>0)')

    df_prev = query("""
        SELECT title_id, title, author, year, death_year, (death_year+71) as dp_eu_year,
               has_french_vf, french_title, dp_us, dp_us_reason,
               award_count, award_score, awards,
               annualviews, isfdb_tags, synopsis, nb_langues_vf, langues_vf,
               "type" as work_type
        FROM works WHERE """+' AND '.join(where_p)+"""
        ORDER BY death_year ASC, annualviews DESC NULLS LAST""", params_p)

    if len(df_prev)==0:
        st.info('Aucune œuvre trouvée pour ces critères.')
    else:
        st.metric('Œuvres concernées', len(df_prev))
        st.markdown('---')
        for dp_year in range(y_min, y_max+1):
            df_year = df_prev[df_prev['dp_eu_year']==dp_year]
            if len(df_year)==0: continue
            st.subheader('🗓 '+str(dp_year)+' — '+str(len(df_year))+' œuvre(s)')
            st.caption('Auteurs morts en '+str(dp_year-71))
            authors_year = df_year['author'].unique()
            st.markdown('**Auteurs** : '+', '.join(authors_year[:10])+
                        (' +'+str(len(authors_year)-10)+' autres' if len(authors_year)>10 else ''))
            for _, row in df_year.iterrows():
                with st.container():
                    vf_icon = '🟢' if row['has_french_vf']==1 else '🔴'
                    year_s  = str(int(row['year'])) if row['year'] else '?'
                    st.markdown(vf_icon+' **'+str(row['title'])+'**  ·  '
                                +str(row['author'])+'  ·  '+year_s
                                +'  ·  *'+str(row.get('work_type','?'))+'*')
                    badges = ''
                    if row['dp_us']==1:   badges += '<span class="dp">✅ Déjà DP US</span> '
                    elif row['dp_us']==0: badges += '<span class="award">🔒 Protégé US</span> '
                    if row['award_count'] and int(row['award_count'])>0 and row.get('awards'):
                        badges += '<span class="award">🏆 '+str(int(row['award_count']))+' award(s)</span> '
                    if row['award_score'] and int(row['award_score'])>0:
                        badges += '<span class="award">⭐ score '+str(int(row['award_score']))+'</span> '
                    if row['nb_langues_vf'] and int(row['nb_langues_vf'])>0:
                        badges += '<span class="tag">🌍 '+str(int(row['nb_langues_vf']))+' langues</span> '
                    if row['isfdb_tags']:
                        for tag in str(row['isfdb_tags']).split(',')[:3]:
                            if tag.strip(): badges += '<span class="tag">'+tag.strip()+'</span> '
                    if badges: st.markdown(badges, unsafe_allow_html=True)
                    if row['synopsis']:
                        st.caption('📖 '+str(row['synopsis'])[:200]+'…')
                    if st.button('📄 Détail', key='prev_'+str(row['title_id'])):
                        r_full = query("SELECT w.*, e.status, e.priority, e.score, e.note FROM works w LEFT JOIN editorial e ON w.title_id=e.title_id WHERE w.title_id=?", (int(row['title_id']),))
                        if not r_full.empty: show_fiche(r_full.iloc[0].to_dict())
                    elif row['has_french_vf']==0 and row['annualviews']:
                        st.caption('👁 '+str(int(row['annualviews']))+'/an')
                st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE SÉLECTION ÉDITORIALE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == '📋 Sélection éditoriale':
    with st.sidebar:
        st.subheader('Filtres')
        df_grps  = query("SELECT DISTINCT groupe FROM editorial WHERE groupe IS NOT NULL AND groupe!='' ORDER BY groupe")
        grp_opts = ['Tous']+df_grps['groupe'].tolist()
        filter_status   = st.selectbox('Statut', ['Tous']+ED_STATUTS)
        filter_groupe   = st.selectbox('Groupe', grp_opts)
        filter_priority = st.selectbox('Priorité', ['Toutes']+list(PRIORITY_LABELS.values()))
        sort_ed         = st.selectbox('Trier par', [
            'e.updated_at DESC','e.score DESC','e.priority ASC','w.annualviews DESC','w.year ASC'])

    st.title('📋 Sélection éditoriale')
    where_ed, params_ed = ['1=1'], []
    if filter_status!='Tous':
        where_ed.append('e.status=?'); params_ed.append(filter_status)
    if filter_groupe!='Tous':
        where_ed.append('e.groupe=?'); params_ed.append(filter_groupe)
    if filter_priority!='Toutes':
        where_ed.append('e.priority=?'); params_ed.append(PRIORITY_REV[filter_priority])

    df_ed = query("""
        SELECT w.title_id, w.title, w.author, w.year, w."type" as work_type,
               w.dp_eu, w.dp_us, w.awards, w.award_count, w.synopsis,
               w.isfdb_tags, w.annualviews, w.has_french_vf,
               w.rating, w.fantlab_rating, w.nb_reviews, w.goodreads_id,
               e.status, e.note, e.updated_at,
               COALESCE(e.priority,3) as priority,
               COALESCE(e.score,0) as score,
               e.groupe, e.tags_maison
        FROM editorial e JOIN works w ON e.title_id=w.title_id
        WHERE """+' AND '.join(where_ed)+"""
        ORDER BY """+sort_ed, params_ed)

    if len(df_ed)==0:
        st.info('Aucune œuvre. Utilisez le Catalogue pour marquer des œuvres.')
    else:
        mc1,mc2,mc3,mc4,mc5 = st.columns(5)
        mc1.metric('Total',        len(df_ed))
        mc2.metric('Sélectionnés', int((df_ed['status']=='Sélectionné').sum()))
        mc3.metric('En cours',     int((df_ed['status']=='En cours').sum()))
        mc4.metric('Score moy.',   round(pd.to_numeric(df_ed['score'],errors='coerce').mean(),1) if pd.to_numeric(df_ed['score'],errors='coerce').sum()>0 else '—')
        mc5.metric('Groupes',      df_ed['groupe'].nunique())

        if filter_groupe=='Tous':
            grp_view = df_ed.groupby(df_ed['groupe'].fillna('(sans groupe)')).size().reset_index(name='n')
            if len(grp_view)>0:
                st.markdown('**Groupes** : '+' · '.join(
                    f"**{row['groupe']}** ({row['n']})" for _,row in grp_view.iterrows()))
        st.markdown('---')

        for _, row in df_ed.iterrows():
            tid      = int(row['title_id'])
            edit_key = f'edit_{tid}'
            del_key  = f'cdel_{tid}'
            for k in [edit_key, del_key]:
                if k not in st.session_state: st.session_state[k] = False

            with st.container():
                col_info, col_actions = st.columns([4,2])
                with col_info:
                    vf_icon = '🟢' if row['has_french_vf']==1 else '🔴'
                    year_s  = str(int(row['year'])) if row['year'] else '?'
                    st.markdown(f"{vf_icon} **{row['title']}**  ·  {row['author']}  ·  {year_s}  ·  *{row.get('work_type','?')}*")
                    badges = ''
                    if row.get('dp_eu')==1 and row.get('dp_us')==1: badges += '<span class="dp">✅ DP EU+US</span> '
                    elif row.get('dp_eu')==1:                        badges += '<span class="dp">🇪🇺 DP EU</span> '
                    if row['award_count'] and int(row['award_count'])>0 and row.get('awards'):
                        badges += f'<span class="award">🏆 {int(row["award_count"])} award(s)</span> '
                    if row.get('groupe'):
                        badges += f'<span class="list">📁 {row["groupe"]}</span> '
                    if badges: st.markdown(badges, unsafe_allow_html=True)
                    score    = int(row['score'])    if row['score']    else 0
                    priority = int(row['priority']) if row['priority'] else 3
                    st.caption('⭐'*score+'☆'*(10-score)+'  ·  '+PRIORITY_LABELS[priority]+'  ·  '+str(row['status']))
                    if row.get('tags_maison'): st.caption('🏷 '+str(row['tags_maison']))
                    if row.get('note'):        st.caption('📝 '+str(row['note'])[:300])

                with col_actions:
                    cur = row['status'] if row['status'] in ED_STATUTS else 'À évaluer'
                    new = st.selectbox('Statut', ED_STATUTS, index=ED_STATUTS.index(cur), key=f'ed_s_{tid}')
                    if new!=cur:
                        run("UPDATE editorial SET status=?,updated_at=datetime('now') WHERE title_id=?", (new,tid))
                        st.rerun()
                    btn1, btn2 = st.columns(2)
                    if btn1.button('✏️', key=f'eb_{tid}', help='Éditer'):
                        st.session_state[edit_key] = not st.session_state[edit_key]; st.rerun()
                    if not st.session_state[del_key]:
                        if btn2.button('🗑️', key=f'db_{tid}', help='Supprimer'):
                            st.session_state[del_key] = True; st.rerun()
                    else:
                        st.warning('Confirmer la suppression ?')
                        dy, dn = st.columns(2)
                        if dy.button('✅', key=f'dy_{tid}'):
                            run('DELETE FROM editorial WHERE title_id=?', (tid,))
                            st.session_state[del_key] = False; st.rerun()
                        if dn.button('❌', key=f'dn_{tid}'):
                            st.session_state[del_key] = False; st.rerun()

            if st.session_state.get(edit_key):
                with st.container():
                    st.markdown(f'##### ✏️ {row["title"]}')
                    fe1, fe2, fe3 = st.columns(3)
                    with fe1:
                        new_score = st.slider('Score /10', 0, 10,
                                              int(row['score']) if row['score'] else 0, key=f'sc_{tid}')
                        new_prio  = st.selectbox('Priorité', list(PRIORITY_LABELS.values()),
                                                 index=(int(row['priority'])-1) if row['priority'] else 2,
                                                 key=f'pr_{tid}')
                    with fe2:
                        all_grps = query("SELECT DISTINCT groupe FROM editorial WHERE groupe IS NOT NULL AND groupe!='' ORDER BY groupe")
                        grp_list = ['(sans groupe)']+all_grps['groupe'].tolist()+['➕ Nouveau groupe…']
                        cur_grp  = row.get('groupe') or ''
                        def_idx  = all_grps['groupe'].tolist().index(cur_grp)+1 if cur_grp in all_grps['groupe'].tolist() else 0
                        sel_grp  = st.selectbox('Groupe', grp_list, index=def_idx, key=f'grp_{tid}')
                        if sel_grp=='➕ Nouveau groupe…':
                            sel_grp = st.text_input('Nom du nouveau groupe', key=f'grpn_{tid}')
                        elif sel_grp=='(sans groupe)':
                            sel_grp = ''
                        new_tags_m = st.text_input('Tags maison', value=row.get('tags_maison') or '',
                                                    placeholder='coup de cœur, relire, Turjman…', key=f'tm_{tid}')
                    with fe3:
                        new_note = st.text_area('Note', value=row.get('note') or '', height=130, key=f'nt_{tid}')
                    sv, ca = st.columns([1,4])
                    if sv.button('💾 Sauvegarder', key=f'esv_{tid}'):
                        run("""UPDATE editorial SET score=?,priority=?,groupe=?,tags_maison=?,note=?,
                               updated_at=datetime('now') WHERE title_id=?""",
                            (new_score, PRIORITY_REV[new_prio],
                             sel_grp or None, new_tags_m or None, new_note or None, tid))
                        st.session_state[edit_key] = False; st.success('✅'); st.rerun()
                    if ca.button('Annuler', key=f'eca_{tid}'):
                        st.session_state[edit_key] = False; st.rerun()
            st.divider()

        ex1, ex2 = st.columns(2)
        ex1.download_button('📥 Export CSV (vue actuelle)',
                             df_ed.to_csv(index=False).encode('utf-8'),
                             'selection.csv', 'text/csv')
        if filter_groupe!='Tous':
            ex2.download_button(f'📥 Export groupe "{filter_groupe}"',
                                 df_ed.to_csv(index=False).encode('utf-8'),
                                 f'groupe_{filter_groupe}.csv', 'text/csv')

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE STATS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == '📊 Stats':
    st.title('Statistiques')
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric('Total',         query('SELECT COUNT(*) as n FROM works').iloc[0]['n'])
    c2.metric('DP EU',         query('SELECT COUNT(*) as n FROM works WHERE dp_eu=1').iloc[0]['n'])
    c3.metric('DP EU sans VF', query('SELECT COUNT(*) as n FROM works WHERE dp_eu=1 AND has_french_vf=0').iloc[0]['n'])
    c4.metric('DP EU+US',      query('SELECT COUNT(*) as n FROM works WHERE dp_eu=1 AND dp_us=1 AND has_french_vf=0').iloc[0]['n'])
    c5.metric('Synopsis',      query('SELECT COUNT(*) as n FROM works WHERE synopsis IS NOT NULL').iloc[0]['n'])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader('Par type')
        st.bar_chart(query("""SELECT "type", COUNT(*) as nb FROM works
                              WHERE dp_eu=1 AND has_french_vf=0
                              GROUP BY "type" ORDER BY nb DESC""").set_index('type'))
    with col2:
        st.subheader('Par décennie')
        st.bar_chart(query("""SELECT (year/10)*10 as decade, COUNT(*) as nb FROM works
                              WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND year IS NOT NULL
                              GROUP BY decade ORDER BY decade""").set_index('decade'))

    st.subheader('Top 30 auteurs (romans sans VF)')
    st.dataframe(query("""
        SELECT author, COUNT(*) as romans, SUM(award_count) as awards,
               MIN(year) as debut, MAX(year) as fin, MAX(annualviews) as max_vues
        FROM works
        WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND "type"='novel'
        GROUP BY author ORDER BY romans DESC LIMIT 30"""), use_container_width=True)

    st.subheader('📋 Sélection éditoriale')
    df_ed_stats = query("""
        SELECT e.status, e.groupe, COALESCE(e.priority,3) as priority, COALESCE(e.score,0) as score
        FROM editorial e""")
    if len(df_ed_stats)>0:
        s1,s2,s3 = st.columns(3)
        s1.bar_chart(df_ed_stats.groupby('status').size().rename('n'))
        grp_counts = df_ed_stats[df_ed_stats['groupe'].notna()].groupby('groupe').size().rename('n')
        if len(grp_counts)>0: s2.bar_chart(grp_counts)
        prio_counts = df_ed_stats.groupby('priority').size().rename('n')
        prio_counts.index = [PRIORITY_LABELS.get(i,str(i)) for i in prio_counts.index]
        s3.bar_chart(prio_counts)

    st.markdown('---')
    st.subheader('🔄 Enrichissement Goodreads')

    MIN_SCORE = 10
    gr = query("""
        SELECT
            SUM(CASE WHEN gr_rating IS NOT NULL THEN 1 ELSE 0 END)                          as avec_rating,
            SUM(CASE WHEN gr_searched=1 AND gr_rating IS NULL THEN 1 ELSE 0 END)            as cherche_introuvable,
            SUM(CASE WHEN (gr_searched IS NULL OR gr_searched=0) AND (dp_eu=1 OR dp_us=1)
                     AND has_french_vf=0 AND award_count>0 THEN 1 ELSE 0 END)               as restants_p1,
            SUM(CASE WHEN (gr_searched IS NULL OR gr_searched=0) AND (dp_eu=1 OR dp_us=1)
                     AND has_french_vf=0 AND (award_count IS NULL OR award_count=0)
                     AND (COALESCE(annualviews,0)/1000.0
                          + COALESCE(nb_langues_vf,0)*5
                          + COALESCE(award_score,0)) >= 10 THEN 1 ELSE 0 END)               as restants_p2,
            SUM(CASE WHEN gr_summary IS NOT NULL THEN 1 ELSE 0 END)                         as avec_summary,
            SUM(CASE WHEN gr_reviews_text IS NOT NULL THEN 1 ELSE 0 END)                    as avec_reviews
        FROM works
    """).iloc[0]

    total_cibles = int(gr['avec_rating']) + int(gr['cherche_introuvable']) + int(gr['restants_p1']) + int(gr['restants_p2'])
    done         = int(gr['avec_rating']) + int(gr['cherche_introuvable'])
    pct          = done / total_cibles * 100 if total_cibles > 0 else 0

    g1,g2,g3,g4 = st.columns(4)
    g1.metric('Avec rating',    int(gr['avec_rating']))
    g2.metric('Avec summary',   int(gr['avec_summary']))
    g3.metric('Avec critiques', int(gr['avec_reviews']))
    g4.metric('Introuvables',   int(gr['cherche_introuvable']))

    st.progress(pct/100, text=f'Progression globale : {pct:.1f}% ({done}/{total_cibles} traités)')

    rp1, rp2 = int(gr['restants_p1']), int(gr['restants_p2'])
    b1, b2 = st.columns(2)
    b1.progress(
        1 - rp1 / max(rp1 + done, 1),
        text=f'P1 — Primés DP sans VF : {rp1} restants'
    )
    b2.progress(
        1 - rp2 / max(rp2 + done, 1),
        text=f'P2 — Score ≥ {MIN_SCORE} DP sans VF : {rp2} restants'
    )

    # Dernière exécution du batch
    import os
    log_path = '/app/data/20_gr_batch.log'
    if os.path.exists(log_path):
        with open(log_path) as lf:
            lines = lf.readlines()
        last_run   = next((l.strip() for l in lines if '===' in l and 'gr_batch' in l.lower()), None)
        last_stats = [l.strip() for l in lines if 'Trouvés' in l or 'Bloqués' in l or 'Estimation' in l or 'Total DB' in l][-4:]
        if last_run:
            st.caption(f'Dernier run : {last_run}')
        if last_stats:
            st.code('\n'.join(last_stats), language=None)
    else:
        st.caption('Batch pas encore lancé (20_gr_batch.py)')
