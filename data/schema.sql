CREATE TABLE [editorial] (
   [title_id] INTEGER PRIMARY KEY,
   [status] TEXT,
   [note] TEXT,
   [ai_note] TEXT,
   [updated_at] TEXT
, priority INTEGER DEFAULT 3, score INTEGER DEFAULT 0, groupe TEXT, tags_maison TEXT);

CREATE TABLE [works] (
   [title_id] INTEGER PRIMARY KEY,
   [title] TEXT,
   [author] TEXT,
   [year] INTEGER,
   [type] TEXT,
   [birthplace] TEXT,
   [author_lang_id] INTEGER,
   [birth_year] TEXT,
   [death_year] TEXT,
   [dp_eu] INTEGER,
   [dp_us] INTEGER,
   [dp_us_reason] TEXT,
   [has_french_vf] INTEGER,
   [french_title] TEXT,
   [series] TEXT,
   [series_num] INTEGER,
   [langues_vf] TEXT,
   [nb_langues_vf] INTEGER,
   [nb_editions] INTEGER,
   [awards] TEXT,
   [award_count] INTEGER,
   [isfdb_url] TEXT
, isfdb_tags TEXT, isfdb_lists TEXT, synopsis TEXT, rating TEXT, annualviews TEXT, goodreads_id TEXT, nb_reviews TEXT, award_score TEXT, wikipedia_url TEXT, translator TEXT, translator_dp TEXT, fantlab_rating TEXT, fantlab_votes TEXT, ol_rating TEXT, ol_votes TEXT, first_pub_year TEXT, last_vf_year TEXT, last_vf_publisher TEXT, last_vf_title TEXT, synopsis_source TEXT DEFAULT 'isfdb', ol_description TEXT, ol_subjects TEXT, ol_key TEXT, wp_searched INTEGER DEFAULT 0, ol_searched INTEGER DEFAULT 0, lccn TEXT, dp_checked INTEGER DEFAULT 0, dp_us_source TEXT, ht_rights_code TEXT, ht_id TEXT, ol_oclc TEXT, gr_rating REAL, gr_votes INTEGER, gr_toread INTEGER, gr_reviews_text TEXT, gr_summary TEXT, gr_searched INTEGER DEFAULT 0, guardian_url TEXT, guardian_title TEXT, guardian_date TEXT, guardian_snippet TEXT, guardian_searched INTEGER DEFAULT 0);

CREATE TABLE 'works_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;

CREATE TABLE 'works_fts_data'(id INTEGER PRIMARY KEY, block BLOB);

CREATE TABLE 'works_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);

CREATE TABLE 'works_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;

CREATE INDEX [idx_works_year]
    ON [works] ([year]);

CREATE INDEX [idx_works_dp_eu]
    ON [works] ([dp_eu]);

CREATE INDEX [idx_works_dp_us]
    ON [works] ([dp_us]);

CREATE INDEX [idx_works_has_french_vf]
    ON [works] ([has_french_vf]);

CREATE INDEX [idx_works_author]
    ON [works] ([author]);

CREATE INDEX [idx_works_type]
    ON [works] ([type]);

CREATE INDEX [idx_works_series]
    ON [works] ([series]);

CREATE TRIGGER [works_ai] AFTER INSERT ON [works] BEGIN
  INSERT INTO [works_fts] (rowid, [title], [author], [series]) VALUES (new.rowid, new.[title], new.[author], new.[series]);
END;

CREATE TRIGGER [works_ad] AFTER DELETE ON [works] BEGIN
  INSERT INTO [works_fts] ([works_fts], rowid, [title], [author], [series]) VALUES('delete', old.rowid, old.[title], old.[author], old.[series]);
END;

CREATE TRIGGER [works_au] AFTER UPDATE ON [works] BEGIN
  INSERT INTO [works_fts] ([works_fts], rowid, [title], [author], [series]) VALUES('delete', old.rowid, old.[title], old.[author], old.[series]);
  INSERT INTO [works_fts] (rowid, [title], [author], [series]) VALUES (new.rowid, new.[title], new.[author], new.[series]);
END;

