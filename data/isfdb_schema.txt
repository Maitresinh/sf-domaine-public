author_views: author_id, views, annual_views
authors: author_id, author_canonical, author_legalname, author_birthplace, author_birthdate, author_deathdate, note_id, author_wikipedia, author_views, author_imdb, author_marque, author_image, author_annualviews, author_lastname, author_language, author_note
authors_by_debut_date: row_id, debut_year, author_id, title_count
award_cats: award_cat_id, award_cat_name, award_cat_type_id, award_cat_order, award_cat_note_id
award_titles_report: award_title_id, title_id, score, year, decade, title_type
award_types: award_type_id, award_type_code, award_type_name, award_type_wikipedia, award_type_note_id, award_type_by, award_type_for, award_type_short_name, award_type_poll, award_type_non_genre
awards: award_id, award_title, award_author, award_year, award_ttype, award_atype, award_level, award_movie, award_type_id, award_cat_id, award_note_id
bad_images: pub_id, image_url
canonical_author: ca_id, title_id, author_id, ca_status
changed_verified_pubs: change_id, pub_id, sub_id, verifier_id, change_time
cleanup: cleanup_id, record_id, report_type, resolved, record_id_2
deleted_secondary_verifications: deletion_id, pub_id, reference_id, verifier_id, verification_time, deleter_id, deletion_time
directory: directory_id, directory_mask, directory_index
emails: email_id, author_id, email_address
front_page_pubs: pub_id
history: history_id, history_time, history_table, history_record, history_field, history_submission, history_submitter, history_reviewer, history_from, history_to
identifier_sites: identifier_site_id, identifier_type_id, site_position, site_url, site_name
identifier_types: identifier_type_id, identifier_type_name, identifier_type_full_name
identifiers: identifier_id, identifier_type_id, identifier_value, pub_id
isbn_ranges: start_value, end_value, prefix_length, publisher_length
languages: lang_id, lang_name, lang_code, latin_script
license_keys: key_id, user_id, license_key
magazine: Mag_Code, Mag_Name, Mag_Desc
metadata: metadata_schemaversion, metadata_counter, metadata_dbstatus, metadata_editstatus
most_reviewed: most_reviewed_id, title_id, year, decade, reviews
mw_actor: actor_id, actor_user, actor_name
mw_revision_actor_temp: revactor_rev, revactor_actor, revactor_timestamp, revactor_page
mw_user: user_id, user_name, user_real_name, user_password, user_newpassword, user_email, user_touched, user_token, user_email_authenticated, user_email_token, user_email_token_expires, user_registration, user_newpass_time, user_editcount, user_password_expires
mw_user_groups: ug_user, ug_group, ug_expiry
notes: note_id, note_note
primary_verifications: verification_id, pub_id, user_id, ver_time, ver_transient
pseudonyms: pseudo_id, author_id, pseudonym
pub_authors: pa_id, pub_id, author_id
pub_content: pubc_id, title_id, pub_id, pubc_page
pub_series: pub_series_id, pub_series_name, pub_series_wikipedia, pub_series_note_id
publishers: publisher_id, publisher_name, publisher_wikipedia, note_id
pubs: pub_id, pub_title, pub_tag, pub_year, publisher_id, pub_pages, pub_ptype, pub_ctype, pub_isbn, pub_frontimage, pub_price, note_id, pub_series_id, pub_series_num, pub_catalog
recognized_domains: domain_id, domain_name, site_name, site_url, linking_allowed, required_segment, explicit_link_required
reference: reference_id, reference_label, reference_fullname, pub_id, reference_url
reports: row_id, report_id, report_param, report_data
self_approvers: user_id
series: series_id, series_title, series_parent, series_type, series_parent_position, series_note_id
sfe3_authors: sfe3_authors_id, url, author_name, resolved
submissions: sub_id, sub_state, sub_type, sub_data, sub_time, sub_reviewed, sub_submitter, sub_reviewer, sub_reason, sub_holdid, affected_record_id
tag_mapping: tagmap_id, tag_id, title_id, user_id
tag_status_log: change_id, tag_id, user_id, new_status, timestamp
tags: tag_id, tag_name, tag_status
templates: template_id, template_name, template_display, template_type, template_url, template_mouseover
title_awards: taw_id, award_id, title_id
title_relationships: tr_id, title_id, review_id, series_id, translation_id
title_views: title_id, views, annual_views
titles: title_id, title_title, title_translator, title_synopsis, note_id, series_id, title_seriesnum, title_copyright, title_storylen, title_ttype, title_wikipedia, title_views, title_parent, title_rating, title_annualviews, title_ctl, title_language, title_seriesnum_2, title_non_genre, title_graphic, title_nvz, title_jvn, title_content
trans_authors: trans_author_id, trans_author_name, author_id
trans_legal_names: trans_legal_name_id, trans_legal_name, author_id
trans_pub_series: trans_pub_series_id, trans_pub_series_name, pub_series_id
trans_publisher: trans_publisher_id, trans_publisher_name, publisher_id
trans_pubs: trans_pub_id, trans_pub_title, pub_id
trans_series: trans_series_id, trans_series_name, series_id
trans_titles: trans_title_id, trans_title_title, title_id
user_languages: user_lang_id, user_id, lang_id, user_choice
user_preferences: user_pref_id, user_id, concise_disp, display_all_languages, default_language, covers_display, suppress_translation_warnings, suppress_bibliographic_warnings, cover_links_display, keep_spaces_in_searches, suppress_help_bubbles, suppress_awards, suppress_reviews, display_post_submission, display_title_translations
user_sites: user_site_id, site_id, user_id, user_choice
user_status: user_status_id, user_id, last_changed_ver_pubs, last_viewed_ver_pubs
verification: verification_id, pub_id, reference_id, user_id, ver_time, ver_status
votes: vote_id, title_id, user_id, rating
web_api_users: user_id
webpages: webpage_id, author_id, publisher_id, url, pub_series_id, title_id, award_type_id, series_id, award_cat_id, pub_id
websites: site_id, site_name, site_url, site_isbn13
