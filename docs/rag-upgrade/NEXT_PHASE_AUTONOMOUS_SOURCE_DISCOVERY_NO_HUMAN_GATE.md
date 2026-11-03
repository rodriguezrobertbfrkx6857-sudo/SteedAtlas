# SteedAtlas / 百骑谱 — Next Phase: Autonomous Evidence Acquisition, No Human Approval Gate

> User-directed override of the earlier G1/G4/G6 manual-curation bottleneck. Written 2026-11-02. **This is a task specification, not a completion claim.**
>
> **Priority: deliver a useful knowledge-backed website.** Work autonomously on a local copy, using public, reusable datasets and documented APIs. Do not require human review, two-person annotation or curator approval to proceed with acquisition, evidence-backed browsing and source-attributed answers. Do not falsely label machine checks as human review or historical truth.
>
> Preserve the original black-and-gold frontend, all legacy business features and video factory. This document supersedes conflicting "wait for manual approval before historical RAG works" instructions in the 2026-11-02 roadmap, but **does not** waive privacy, copyright, payment authorization, production deployment or irreversible-deletion restrictions.

## A. Why this is necessary — verified code baseline

On branch feat/rag-core-major-upgrade at f04fff3b, KnowledgeRepository, EvidenceSearch, AnswerService, knowledge_api and RULE_BASED ResearchAgent already exist. The local evidence report recorded 100 editorial records, 3 DRAFT claims, zero approved/citable claims; 40 unlabelled complex questions; 62 passed local backend tests; no live LLM/Jev call. **This was an engineering success but a practical content gap**. We should no longer wait for human curation to have usable historical-source browsing and grounded attribution.

Existing source and answer acceptance logic tightly couples usable citation to review_state=APPROVED. Refactor that conflation; do not forge an APPROVED human approval. Existing "matched_horse", "personality_match", "recommended_product", "recommendation_strategy" returned None by the new AnswerService; preserve or restore relevant, optional culture/personalization functions in their own non-factual lane. Existing literature scope and long-range temporal/multi-hop routing are incomplete.

## B. Source acquisition shortlist — retrieve only from permitted channels

**Start with the real needs of the 100 catalogued horses and their historical/literary works, NOT a massive indiscriminate crawl.** For each upstream source record identifier, title, work, author/compiler, exact edition/version, page/section/revision, content hash, provenance URL, acquisition date, rights/license evidence, attribution and changes.

1. **Wikisource via MediaWiki APIs / licensed exports**: prefer exact stable revision IDs, original Chinese work, chapter/volume, meaningful paragraph/spans. Official guidance:
   - https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page
   - https://www.mediawiki.org/wiki/API:Revisions
   - https://en.wikisource.org/wiki/Wikisource:Reusing_Wikisource_content
   - https://www.mediawiki.org/wiki/API:REST_API/Policies
   Use compliant User-Agent and rate limiting, respect page-specific work/edition rights; the text of an ancient work can be public-domain while a modern translation, note, scan, edition or platform metadata differs.
2. **Wikidata for entity discovery and aliases**, not ground truth about detailed historical events. CC0 structured data; use entity search / constrained SPARQL, avoid regex-heavy broad SPARQL, record QIDs and source references when present: https://www.wikidata.org/wiki/Wikidata:Reuse .
3. **Hugging Face candidate: gujilab/chinese-classical-corpus** (also investigate forks/duplicates and actual canonical origin): https://huggingface.co/datasets/gujilab/chinese-classical-corpus . The card advertises material from Shiji, Sanguozhi, history texts and translation/parsing data. **Treat license claims as UNVERIFIED until upstream lineage is checked.** Its card lists upstream providers with different terms, including ctext.org. Use only a version and subset with permitted use; do not let a dataset-card "CC0" field erase upstream obligations or source identity. Prefer the original historical-text subset rather than synthetic instruction translations for factual citations. Report any conflicting permission evidence and skip ambiguous segments rather than block the whole upgrade.
4. **Kaggle datasets and open GitHub collections** as secondary discovery. Search for classical source editions, person–horse/event relations and work-specific text. Before download, inspect data card, version, licence, source genealogy, whether text is generated or OCR, and whether the provenance can be resolved to an actual edition. Kaggle is a hosting platform, not a guarantee of quality, license or factual reliability.
5. **Gutenberg** only for suitable books and allowed mirrors/robot feeds; public-domain status varies by jurisdiction and work; use documented robot policy: https://www.gutenberg.org/policy/robot_access.html and https://www.gutenberg.org/policy/permission.html .
6. **Chinese Text Project** can be a reference only via terms-compliant authorized API when available. **No scraping, CAPTCHA bypass, rotating IPs or prohibited bulk downloads**. Official FAQ specifically warns about automatic download software; permitted API is usage- and authentication-limited: https://ctext.org/faq and https://ctext.org/tools/api/ens . If unavailable, select other sources and continue.

Data ordering: named horses/aliases first, then the known relevant chapters and works (e.g., Sanguozhi, Shiji and literary accounts), then breadth across the 100-entry catalogue. Distinguish catalogue's historically attested figures from purely literary, folkloric, creative or editorial entities. Do not fabricate evidence for intrinsically invented entries.

## C. An autonomous, conservative evidence state machine

**Do not equate "text exists", "source is accessible", "source is licensed", "claim is supported", and "historical event happened".**

Store independent axes:

- acquisition_state: DISCOVERED / FETCHED / PARSED / FAILED
- provenance_state: EXACT_REVISION_MATCH / LOCATOR_MATCH / SOURCE_ONLY / UNKNOWN
- rights_state: PERMITTED_REUSE / ATTRIBUTION_REQUIRED / UNKNOWN / RESTRICTED
- machine_validation: VERIFIED_QUOTATION / AUTOMATED_ATTRIBUTION / CORROBORATED_WITH_INDEPENDENT_SOURCE / CONFLICTING / UNVERIFIED
- epistemic_kind: HISTORICAL_SOURCE_REPORT / LITERARY_NARRATIVE / FOLK_TRADITION / EDITORIAL / CREATIVE
- human_review_state: NOT_REVIEWED / REVIEWED (only use REVIEWED if an actual eligible human reviewed it).

**No manual approval gate:** when (a) the exact public source/version and actual quote span can be retrieved, (b) the content/locator hashes and rights policy pass, and (c) access policy permits, the excerpt enters an **AUTO_VERIFIED_SOURCE** presentation track, and the product may show attributed quotations immediately. A source's claim about a historical event is still an attributed statement, not proof of the event's truth. A source URL alone or dataset title is insufficient. If content rights cannot be verified, skip copying that text and retain permitted metadata/links only.

Allow machine-derived ClaimCandidate / atomic claims with checkable quotation links, independently validated syntax/span/entity references and no human requirement to generate candidate links. Accept them for source-attributed retrieval under a machine-validated label; do **not** mark staff APPROVED, invent a curator, overwrite legacy approval event, or claim expert gold. When support cannot be checked semantically, label "quoted source relevant but entailment unverified" and return the quote, not an embellished conclusion.

Keep the original APPROVED path for future curated data, but no longer block normal user browsing or source-attributed Q&A merely because all new claims lack a human approval. Change the citation guard to a **transparent evidence-use policy**, not a global bypass. Modes: SOURCE_BROWSE / SOURCE_ATTRIBUTED / LITERARY_ATTRIBUTED / SOURCE_CONFLICT / INSUFFICIENT / CLARIFY. The client can still consume legacy AnswerEnvelope fields, with additional verification labels and versions.

Algorithmic checks permitted without human review: exact quote presence in fetched revision, locator/offset checks, deterministic content hashes, source-version pinning, permission/visibility tests, domain and DOI/URL consistency, alias normalization, duplicate/source-dependence clustering, negative/control questions, contradiction candidates, cross-version diffs. LLM/NLI may help find candidates, but model confidence is not historical truth or proof of entailment. Any model-based judgement must be clearly labeled.

## D. End-to-end ingestion and operational path (implement, not merely propose)

1. Discovery: for each canonical entity and aliases, identify target works and source candidates from permitted collections. Track hit/miss and provenance. Avoid unbounded web searching.
2. License/provenance gate: machine-readable and documented rights policy; record license, required attribution, permitted excerpting. Ambiguous candidates go to QUARANTINED, while the job automatically continues to other providers.
3. Fetch/parser: stable API versions/revisions or versioned dataset files; checksum, charset, traditional/simplified mapping with ORIGINAL UNMODIFIED text preserved. Preserve chapter/volume and original character offsets; normalized search text is a derivative, not the citation text.
4. Entity linking + source segmentation: stable IDs Horse/Person/Event/Work; canonical aliases, false-positive and same-name ambiguity handling, chronological/work/edition relations. Use actual text paragraphs, not arbitrary short chunks for citations.
5. Claim candidates and evidence graph: quoted passage plus claim candidate, distinction of work attribution and historical reality, relation SUPPORTS/MENTIONS/CONTRADICTS/INDETERMINATE. For unresolved support present as source excerpts. Track quotation/copy chains; 4 copied pages do not count as 4 independent witnesses.
6. Atomic/idempotent import to **isolated local DB copy**: source version, immutable revision, unique source+locator+hash, incremental repeatable upsert, no removal of old business data or previously curated evidence. Corrupted/uncertain entries fail closed and quarantine with reasons.
7. Unified retrieval and AnswerService: default knowledge RAG is usable over AUTO_VERIFIED_SOURCE even with zero human APPROVED claims, with accurate source attribution and calibrated refusal. Restore separate helpful culture/story/product recommendation lane, opt-in/appropriate, never feeding product copy back into evidence.
8. Research Agent: enable bounded local source discovery, retrieval, comparison and provenance gap-filling, with real tool traces. It can autonomously add permitted source records and machine-validated excerpts to the knowledge index; destructive actions, publishing, deployment and paid APIs still require separate authorization. Optional learned/Jev/LLM routers after baseline; no fake LIVE_LLM.
9. Regeneration/invalidation: if a source revision/license/visibility changes or source becomes unreachable, mark dependent citations stale, downgrade or block use, and update retrieval; cache/answer audits must not leak now-private content. Avoid serving old approved conclusions without rechecking machine/source status.
10. UI: retain ORIGINAL_BLACK_GOLD. Evidence chips, excerpt links and status labels integrate locally into current black/gold chat/atlas. No "light museum" redesign or replacing compiled assets. Functionality check of original assistant recommendations, login, gacha/collection, commerce sandbox, videos.

## E. Practical batching — accelerate the site, not the bureaucracy

- **Milestone M1:** fully automated source pipeline on the three flagship entries (Chitu, Wuzhui, Dilu). Actual sources, exact excerpts, rights-safe links, attribution and source-verified answers visible from original chat. This must run without any human approver or external paid model. If one source blocked, use an alternate permitted provider; never fake a quote.
- **Milestone M2:** extend entity/work-specific discovery to the real 100-entry catalogue. Report honestly: verified excerpt coverage, source-only links, unsupported editorial/creative records, ambiguous aliases, blocked licenses. Do not invent sources to reach 100/100. Users must still get safe source-backed browsing for supported entities.
- **Milestone M3:** make real user Q&A stronger: literary/historical distinction, common alias questions, source comparison, source-dependent duplicates, uncertain/no-answer, multi-entity and follow-up. Full original-site demo and regression tests. Restore assistant personalization/product feature only outside factual evidence mode.
- **Milestone M4:** independent engineering and evaluation run. Use a reproducible source-based candidate QA set; tests that do not require a human label can PASS for version/span/permissions/citations/idempotence/invalidation. **Do not report gold-standard historical accuracy, inter-annotator agreement or expert citation accuracy without genuine labels.** Optional automatic judges are proxy metrics with transparent limitations.
- **Milestone M5 (optional):** hybrid/Dense/RRF, real LLM research agent and Jev comparisons only when external services are explicitly authorized, privacy/terms checked, and reliable evaluation supports a real net benefit. No need to wait for M5 to ship a useful local RAG experience.

### Deliverables and acceptance

Files under docs/rag-upgrade/, scripts/, tests/, experiments/ and reports/rag-upgrade/ as appropriate:
- SOURCE_PROVIDER_INVENTORY.md with actual URLs/API/data-set commits, version, rights, successful/failed trials and retry behavior.
- automated import modules and scripts with dry-run, limited batch parameters, logs, idempotence, rollback and no overbroad crawl.
- corpus_coverage.json counting exact source references, machine-verified quote spans, ambiguous/restricted items, human reviewed=0 if so; by entity and by provenance level.
- citeable sample requests and responses proving RAG from original UI works without APPROVED, while status says **MACHINE_VERIFIED** or **ATTRIBUTED_SOURCE** and never **HUMAN_REVIEWED**.
- no hallucinated historical answers or fake annotations; negative tests for misquote, wrong edition, mismatch offset, wrong horse, duplicate sources, rights constraints, private data, prompt injection and stale evidence.
- git commits, actual test commands, screenshots before/after, user-facing acceptance demo, honest PASS/FAIL/BLOCKED and next-phase issues.

**Success is not getting 100 fabricated “approved” facts. Success is a working, well-sourced, transparently machine-verified archive assistant with a high coverage of authentic content, no human approval bottleneck, preserved original website and reproducible proof.**

## F. Critical extra caveats

- Wikidata describes entities/relations, but a Wikidata statement is **not** a direct passage from a historical document; keep it discoverable and separately labeled.
- Hugging Face/Kaggle data-card “CC0” can conflict with copyrighted translations, editorial annotations, or upstream service terms. Audit programmatically and log unresolved ambiguity; do not bulk rehost with unknown rights.
- CText has explicit restrictions on automated download software: never get around them, and never silently use forbidden scraping just because the goal is fast.
- No human review means we cannot honestly claim academic gold annotations; use synthetic/property tests, source-verification logs and user-visible epistemic qualifiers instead.
- Subscriptions to an AI coding assistant are not automatic authorization for external third-party API charges or production online deployment.
