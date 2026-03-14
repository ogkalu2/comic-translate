# PIPELINE V2 — System Architecture Overview

## 0. Scope & Goals

**Target users:** Developers, translation groups — not end users.

**Problems solved:**
- Multiple versions of the same comic (pixiv / fan paid / censored / uncensored / revised) cause redundant translation work
- Multi-language output (original + zh_hk + zh_cn + en…) has no unified data model
- NSFW content blocked by cloud API policies
- Scan groups accused of "bruhh ai translate" with no way to prove human editing effort
- Cache and dataset scattered across JSON/scripts with no infra-level schema

**Solution:**
- Block-level data model with multi-source translations (original, official, fan, pipeline versions)
- AI + rule hybrid pipeline (panel detection → OCR → semantic routing → translation → rendering)
- Local-first storage with optional pgvector / Relay Network / blockchain audit

---

## 1. Data Model

### 1.1 Creator / Work

| Field | Description |
|-------|-------------|
| `creator_id` | Author/circle ID: `hash(author_name + representative_work)` |
| `work_id` | Series/volume (e.g. "Series X Vol.1–3") |

Glossary files per creator/work:
- `creator.json` — author's common tone, recurring jokes
- `work.json` — character names, factions, world-building terms

### 1.2 Comic Base (`base_fp`)

Defines "the same work" across all versions.

```
base_fp = sha256(perceptual_hash_all_pages + normalized_title + artist)
```

`base_meta.json`:
- title, artist, creator_id, work_id, original_lang
- references:
  - official: DLsite, publisher translations
  - fan: existing translation group versions
- `glossary/base.json`: work-specific proper nouns

### 1.3 Variant (`variant_id`)

Each file/version of a comic:

```
variant_fp = sha256(raw_file_hash + page_count + censor_signature + source)
```

`variants/{variant_id}/meta.json`:

| Field | Values |
|-------|--------|
| `source` | pixiv / dlsite / fan_zip / local |
| `censored` | true / false |
| `relation_type` | `same_art_diff_censor`, `same_script_diff_edit`, `supersedes` |
| `extra_pages` | cover / omake etc. |

### 1.4 Block (`block_uid`)

Finest granularity — one text unit (speech / narration / SFX / credit).

```
block_uid = "{base_fp}:{page}:{panel}:{bubble_idx}"
```

Core schema:

```json
{
  "block_uid": "base_fp:1:3:0",
  "nsfw_flag": true,
  "type": "dialogue|narration|sfx|credit|ui_meta",
  "bbox": [x, y, w, h],

  "original_texts": [
    {"variant_id": "pixiv_free", "lang": "ja", "text": "原文A"},
    {"variant_id": "dlsite_cn", "lang": "zh_cn", "text": "官方簡中"}
  ],

  "translations": {
    "zh_hk": {
      "v1": {
        "text": "pipeline + 人手修訂版",
        "status": "approved",
        "weight": 1.0,
        "history": [
          {"action": "translate", "source": "deepl"},
          {"action": "reference_applied", "source": "zh_cn_official.dlsite"},
          {"action": "manual_edit", "source": "user:alvin"}
        ]
      }
    },
    "zh_cn_official": {
      "dlsite": {
        "text": "官方簡中",
        "status": "reference",
        "source": "dlsite",
        "weight": 1.0
      }
    }
  },

  "semantic_routing": {
    "ner_entities": [{"entity": "佐藤くん", "type": "PERSON", "conf": 0.96}],
    "sfx_detected": true,
    "route": "local_nsfw_glossary"
  },

  "embedding": [0.1, -0.23, "..."]
}
```

---

## 2. Pipeline Stages

### Stage 0 — Fingerprint & Cache

1. Compute `base_fp` (work-level) and `variant_id` (version-level)
2. Cache lookup (local + Relay):
   - `variant_id` hit → use full translation cache
   - `base_fp` hit → use base blocks + new variant mapping, diff-only
   - miss → full pipeline
3. Multi-version detection:
   - High pixel similarity + censor_signature diff → `same_art_diff_censor`
   - Text diff + structural similarity → `same_script_diff_edit`

### Stage 1 — Detection, OCR, Semantic Routing

**1a Panel Detection (Hybrid AI)**
- Primary: YOLOv12 (`mosesb/best-comic-panel-detection`)
- Fallback: DeepPanel / OpenCV
- Non-max suppression + geometric sorting for reading order

**1b Bubble / SFX Detection**
- Comic-Analysis-Toolkit / custom Mask R-CNN
- Heuristics:
  - Large bold deformed text → SFX
  - Small corner text + URL / "翻譯組" → credit

**1c Multi-language OCR**
- Language ID (ja/ko/en/zh…)
- PaddleOCR v5 multi-lang as base
- Low-confidence blocks → GPT-4o vision fallback
- Results written to `original_texts`

**1d Semantic Routing (NSFW + EhTag + NER)**

| Block type | Routing strategy |
|------------|-----------------|
| `credit` / `ui_meta` | No translation, no repaint. Log "removed original credit/ad text" |
| `nsfw_flag=true` + EhTag match | Local-only translation (NSFW table / local LLM), no external API |
| `sfx` | Local SFX corpus |
| Other dialogue | DeepL (bulk) + GPT-4o-mini / Claude (glossary enforcement / tone) |

### Stage 2 — Translation & Versioning

**Source weights:**

| Source | Key | Usage |
|--------|-----|-------|
| Official (DLsite / publisher) | `*_official.*` | Reference only |
| Fan/scan group | `*_fan.<group>` | Reference only (lower weight) |
| Pipeline output | `zh_hk.v1/v2` | Final render target |
| EhTag / NSFW dictionary | — | NSFW-specific terms |

**Per-block translation flow:**
1. Collect available references (official / fan / self previous)
2. Build prompt with weighted references → generate `translations.<lang>.vN`
3. Record in `history`:
   - `translate` — machine draft source
   - `reference_applied` — used official/fan as reference
   - `manual_edit` — human correction

**User edits as dataset:**
- Each `manual_edit` → save diff for:
  - Fine-tuning local translator / style model
  - Computing `human_edit_coverage` to counter "bruhh ai translate" claims

### Stage 3 — Rendering & Quality Gates & Credit Handling

**Rendering:** Per block, per variant:
- Map bbox (handle censored/uncensored differences)
- Inpaint/overlay text (skip credit blocks)

**Credit / ads:** `type=credit` / `ui_meta` → skip, log removal stats in `TRANSLATION_LOG`

**Quality gates:**
- Glossary hit rate (official → fan → base → EhTag)
- NSFW / SFX consistency
- Text overflow / collision detection
- Optional: Claude/GPT tone review (SFW dialogue only)

---

## 3. Storage Layout

### Local FS (per `base_fp`)

```
cache/
  {base_fp}/
    base_meta.json
    glossary/
      creator.json
      work.json
      base.json
    blocks/
      {block_uid}.json
    variants/
      {variant_id}/
        meta.json
        pages/{i}.png
        renders/{lang}_{version}/{i}.png
    embeddings.json
    TRANSLATION_LOG.json
```

### TRANSLATION_LOG.json

```json
{
  "base_fp": "...",
  "title": "...",
  "artist": "...",
  "stats": {
    "total_blocks": 1234,
    "human_edited_blocks": 850,
    "human_edit_coverage": 0.69,
    "nsfw_blocks": 300,
    "nsfw_local_only_blocks": 300,
    "references_used": {
      "official": 0.40,
      "fan": 0.20
    },
    "removed_credit_blocks": 12
  },
  "sources": {
    "official": [
      {"lang": "zh_cn", "source": "DLsite", "usage": ["glossary", "qa_check"]}
    ],
    "fan": [
      {"lang": "zh_hk", "group": "TsengScans", "usage": ["reference"]}
    ]
  },
  "notes": [
    "NSFW blocks translated via local EhTag/NSFW dictionary only.",
    "Original scan credits/ads removed from final output."
  ]
}
```

---

## 4. Database & Vector (Optional)

### Postgres + pgvector

```sql
CREATE EXTENSION vector;

CREATE TABLE comics (
  base_fp TEXT PRIMARY KEY,
  creator_id TEXT,
  work_id TEXT,
  meta_embedding VECTOR(384),
  hit_count INT DEFAULT 0
);

CREATE TABLE blocks (
  block_uid TEXT PRIMARY KEY,
  base_fp TEXT REFERENCES comics(base_fp),
  embedding VECTOR(384),
  translations JSONB,
  nsfw_flag BOOLEAN
);

CREATE TABLE contributions (
  user_key TEXT,
  base_fp TEXT,
  manual_edits JSONB,
  approved BOOLEAN
);

CREATE INDEX blocks_embedding_idx ON blocks USING ivfflat (embedding vector_cosine_ops);
```

**Use cases:** Similar sentence/SFX search, cross-work translation reuse, community cache hits.

---

## 5. Relay Network (h@H-inspired, Optional)

### Node Types
- **Coordinator:** Node list, scores, language capabilities only
- **Relay Node:** Each participant's own node (Postgres + API)

### API (per Relay Node)

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/comic/fingerprint` | Check if node has translations for base_fp/variant |
| `POST /v1/comic/blocks/query` | Return block translations (sanitized) |
| `POST /v1/comic/blocks/contribute` | Accept new translations (opt-in users only) |

### Privacy (PDPO)
- First connection asks: `opt_in=true` (shared cache + contribute) or `opt_in=false` (local only)
- No collection of: name, email, IP (or immediate hash), location
- Data used only for translation/model improvement, never advertising

---

## 6. Blockchain Audit (Optional)

**On-chain content (hashes only, no content):**

```
translation_hash = SHA256(block_uid || lang || final_text || timestamp)
base_fp_hash = SHA256(base_fp)
```

Plus: `node_id`, `timestamp`, minimal metadata (`lang`, `nsfw_flag`)

**Use cases:**
- Tamper-proof translation history
- Model/dataset provenance (prove which translations trained a model)
- No raw text, translations, or NSFW content on-chain (privacy/deletion compliance)

---

## 7. Cross-References

| Topic | Document |
|-------|----------|
| Script export + QA patch system | [`features/script-export-qa.md`](features/script-export-qa.md) |
| Multi-version fingerprinting | `features/multi-version-fingerprinting.md` (planned) |
| NSFW routing | `features/nsfw-routing.md` (planned) |
| Relay network | `features/relay-network.md` (planned) |
| Legacy translation system plan | [`legacy/manga_translation_system_plan.md`](legacy/manga_translation_system_plan.md) |

---

## 8. Implementation Priority

| Phase | Scope | Depends on |
|-------|-------|------------|
| **1** | Block schema + Script export + QA patch (JSON backend) | — |
| **2** | Multi-version fingerprinting (base_fp, variant_id) | Phase 1 |
| **3** | NSFW routing skeleton + local-only handling | Phase 1 |
| **4** | Postgres + pgvector storage | Phase 1–2 |
| **5** | Relay Network | Phase 4 |
| **6** | Blockchain audit | Phase 5 |
