-- Central doubt forum: FULLTEXT indexes for fuzzy / advanced search (MySQL InnoDB).
-- Safe to re-run: apply script checks index existence.

ALTER TABLE section_doubts
    ADD FULLTEXT INDEX ft_section_doubts_title_body (title, body);

ALTER TABLE section_doubt_answers
    ADD FULLTEXT INDEX ft_doubt_answers_body (body);
