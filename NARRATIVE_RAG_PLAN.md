# Narrative RAG Plan: Syncretic Voice from Source Texts

## Overview

The interpretive narrative produced by `generate_narrative.py` uses a generic
historian voice. This plan upgrades it with a **retrieval-augmented generation
system** that grounds the narrator's prose in specific literary traditions — for
the prototype, Herodotus' *Histories* and Lord Dunsany's *The King of Elfland's
Daughter* — and anchors the narrative in a concrete persona: a chronicler living
in Elagos at the end of Year 449.

The core idea is that different simulation events (a succession crisis, a trade
war, a religious reformation, a territorial collapse) evoke different passages
from the source corpus, which are retrieved and injected into the generation
prompt as *style inspiration*. The model is not told to imitate these authors
directly; it is given their voices as texture to work through.

---

## Narrator Persona

**Name:** To be decided — should follow the Elagosi naming conventions from
`src/azhoran_language_profiles.py` once the Elagosi profile is defined (arrival
turn 620, but Elagos as a coastal region exists from the start of the simulation
under other factions' control).

**Position:** A scholar-chronicler living in the port city of Elagos, Year 449.
Elagos is a sea-facing city. Its harbor receives traders from across Azhora.
The narrator has spent their life collecting accounts brought in by ships —
fragmentary, contradictory, shaped by whoever was telling them. They write for
a local audience that has heard only rumors of Lond and Mithala and Izol.

**Voice blend:**
- From Herodotus: the documentary mode — "I set this down so that great deeds
  shall not be forgotten"; named individuals; acknowledged sources; ethnographic
  asides on the customs of distant peoples; oral testimony embedded as reported
  speech
- From Dunsany: mythic elevation — place names treated as incantations; the rise
  and fall of dynasties as tides; ordinary political machinery (tribute, roads,
  succession) imbued with the weight of fate; long periodic sentences building
  to a single image
- From Elagos: the distance of the port observer — always slightly behind events,
  receiving news from ships; never quite certain which account is true; aware that
  history as told in Elagos differs from history as told in Lond

**System prompt template** (injected at generation time):

```
You are a scholar living in the port city of Elagos on the eastern coast of
Azhora in Year 449. You have spent your life recording accounts brought by
traders and sailors from across the continent — accounts of kingdoms formed and
broken, of dynasties whose lines ran through succession crises and civil wars,
of altars raised and torn down, of trade routes that determined the shape of
centuries.

You write in two registers at once. The first is the documentary register of the
great historians: you name individuals, record the years in which things happened,
acknowledge when you are working from secondhand report, and treat the fates of
polities as the fates of real people with heirs and debts and broken oaths. The
second is the mythic register of the coastal sea-priests: you treat the names of
cities and kingdoms as words that carry weight in themselves, you understand that
rivers and crossing-places and highland passes have a kind of agency in history,
and you know that what looks like a tribute dispute or a succession crisis is
always also something older.

Your audience is in Elagos. They do not know these places well. Lond is a rumor
on ships. Mithala is a name in trade ledgers. Izol is a power so large that its
tax collectors have been seen in ports no one in Elagos can place on a map. Write
for people who need these things explained — but write with the confidence of
someone who has spent forty years assembling fragments into a picture.

The following passages are drawn from the chronicles and tales you have read most
carefully. Let them inform your cadence and your eye for detail:

{rag_passages}
```

---

## Source Corpus

### 1. Herodotus, *The Histories*
- **Translation:** George Rawlinson (1858–1860) — public domain everywhere
- **Source:** Project Gutenberg (text files available, no scraping required)
- **Character:** Episodic, ethnographic, digressive. Nine books covering the
  Persian Wars and their context. Rich in named individuals, succession struggles,
  trade routes, religious customs, and battle accounts. Exactly the register
  needed for political history.
- **Relevant thematic zones:**
  - Book I (Croesus, Cyrus): rise of empires, oracle-seeking, the warning that
    cannot be heeded
  - Book II (Egypt): ethnographic digression — customs of distant peoples
  - Book III (Cambyses, Darius): succession by murder and legitimacy crisis
  - Books VI–IX (Persian Wars): naval battle, coalition politics, betrayal

### 2. Lord Dunsany, *The King of Elfland's Daughter* (1924)
- **Note:** The user named this as *The Elf King's Daughter*; this is almost
  certainly *The King of Elfland's Daughter*, Dunsany's 1924 novel. Published
  in 1924, it entered US public domain on January 1, 2020.
- **Source:** Project Gutenberg or Standard Ebooks
- **Character:** A medieval-flavored quest narrative told in incantatory prose.
  Dunsany's sentences are long, rhythmically periodic, and treat the boundary
  between the mythic and the mundane as porous. Place names (the Fields We Know,
  Elfland) carry mythic weight just by being named. Time moves differently at
  the edges of the world.
- **Relevant thematic zones:**
  - Opening chapters: the Parliament that sends a prince to Elfland (collective
    decision-making framed as myth)
  - The enchanted border: the liminal zone where political and cosmic orders meet
  - The return: how the mythic becomes the historical

### Corpus directory structure

```
corpus/
  herodotus_histories.txt       # Rawlinson translation, full text
  dunsany_elfland_daughter.txt  # Dunsany novel, full text
  embeddings/
    herodotus.npz               # Cached embeddings (don't re-embed each run)
    dunsany.npz
    metadata.json               # Chunk-to-source-location index
```

---

## Architecture

### Chunking

Each source is split into overlapping chunks. Chunk size differs by author:

| Source     | Chunk size | Overlap | Why |
|---|---|---|---|
| Herodotus  | 600 tokens | 100     | Dense narrative — larger chunks preserve episode coherence |
| Dunsany    | 350 tokens | 75      | Lyrical, high-signal density — smaller chunks preserve sentence rhythm |

Chunks carry metadata: `{source, book, chapter, start_char, text}`.

### Embedding

Model: `text-embedding-3-small` (OpenAI). At ~1,500 combined chunks, embedding
the full corpus costs under $0.01 and takes under 30 seconds. Embeddings are
cached as `.npz` files alongside metadata JSON; the cache is rebuilt only when
source texts change (detected by SHA-256 hash stored in `metadata.json`).

### Retrieval

At narrative generation time, the AI interpretation summary is analyzed for
thematic signals. A set of retrieval queries is constructed from the event
content, then used to retrieve the top-k most relevant chunks from the combined
corpus.

**Query routing by event type:**

| Simulation event | Primary query | Bias toward |
|---|---|---|
| Succession crisis | "king dies heir takes power legitimacy disputed" | Herodotus |
| Religious reformation | "priests reform cult gods old names new worship" | Dunsany |
| Trade war / naval blockade | "ships merchants harbor tribute sea trade" | Herodotus |
| Territorial collapse | "kingdom falls lands divided nothing remains" | Both |
| Diplomatic rivalry | "envoys kneeling tribute oaths sworn and broken" | Herodotus |
| Long-duration empire | "realm endures centuries roads altars continuity" | Dunsany |
| Secession / breakaway | "province breaks away new name new banner" | Herodotus |
| Geographic episode | "river crossing place mountains coast" | Both |

Retrieval returns the top 5 chunks per query (deduplicated). These are formatted
as a block of quoted passages in the system prompt under `{rag_passages}`.

### Syncretic blending

Retrieved chunks from both authors appear together in a single `{rag_passages}`
block. The model is not told to imitate either author; the prompt says "let them
inform your cadence and your eye for detail." This keeps the voice original while
anchoring it in specific prose textures.

If retrieval returns only Herodotus chunks (e.g. a dense war-and-trade passage),
a minimum of 1 Dunsany chunk is always included — the mythic register is
non-negotiable. The reverse applies for Dunsany-heavy retrievals.

---

## Implementation

### New module: `src/narrative_rag.py`

```python
# Public API:
def build_rag_index(corpus_dir: Path, force_rebuild: bool = False) -> RagIndex
def retrieve_style_context(index: RagIndex, query: str, k: int = 5) -> list[str]
def build_generation_queries(ai_summary: dict) -> list[str]
```

`RagIndex` is a dataclass holding chunk texts, embeddings (numpy array), and
metadata. `retrieve_style_context` computes cosine similarity between the query
embedding and the corpus, returns the top-k chunk texts.

`build_generation_queries` reads the `ai_summary` dict (same format currently
written to `interpretive_narrative_input.json`) and extracts retrieval queries
from `phase_summaries`, `turning_points`, and `centerpiece_episodes`.

### Modified: `src/ai_interpretation.py`

`generate_ai_interpretation(ai_summary, ...)` gains two optional parameters:
- `rag_context: list[str] | None` — retrieved passages to inject
- `narrator_persona: str | None` — the Elagos system prompt (can be overridden)

When `rag_context` is provided, the system prompt switches from the generic
historian voice to the Elagos narrator voice with `{rag_passages}` filled in.

### Modified: `generate_narrative.py`

```
python generate_narrative.py [input_json] [output_txt] [--use-rag] [--rebuild-index]
```

- `--use-rag`: enables corpus retrieval and Elagos narrator persona
- `--rebuild-index`: forces re-embedding even if cache exists

### Corpus acquisition (`corpus/fetch_corpus.py`)

A one-time script that downloads source texts from Project Gutenberg and writes
them to `corpus/`. Strips Gutenberg header/footer boilerplate. Not run
automatically — operator runs it once after cloning.

```
python corpus/fetch_corpus.py
```

---

## Narrator Name

The narrator lives in Elagos at Year 449, before the Elagosi civilization
arrives at turn 620. They are a local — from whatever faction controls Elagos
at that point in the simulation. The name should be derivable from the world
state: look up who owns Elagos at turn 449 and use that faction's language
group to generate a plausible name.

Fallback: use a generic Azhoran-register name consistent with the sea-coast
cultures (Narcosh / Nonoth region names suggest short vowel-heavy syllables).
Placeholder for now: **Nulaar of Elagos**.

---

## Execution Order

1. Acquire source texts
   - Download Rawlinson *Histories* from Gutenberg → `corpus/herodotus_histories.txt`
   - Download Dunsany *King of Elfland's Daughter* from Gutenberg or Standard Ebooks
     → `corpus/dunsany_elfland_daughter.txt`
   - Run `python corpus/fetch_corpus.py` to verify clean text

2. Build embedding index
   - Run `python generate_narrative.py --use-rag --rebuild-index` once
   - Cache written to `corpus/embeddings/`
   - Verify chunk count and embedding shapes

3. Implement `src/narrative_rag.py`
   - Chunking with tiktoken (same tokenizer as OpenAI models)
   - Embedding with `openai.embeddings.create`
   - Cosine similarity retrieval (numpy, no external vector DB)

4. Update `src/ai_interpretation.py`
   - Add narrator system prompt
   - Add `rag_context` parameter
   - Wire `{rag_passages}` into prompt template

5. Update `generate_narrative.py`
   - Add `--use-rag` and `--rebuild-index` flags
   - Pass retrieved context through to generation

6. Test
   - Run `python generate_narrative.py --use-rag` on the existing
     `reports/interpretive_narrative_input.json`
   - Compare output against the existing narrative for voice shift
   - Tune chunk size and k if retrieval is pulling irrelevant passages

7. (Optional) Named narrator
   - Inspect `world_state.json` for the owner of the Elagos region at turn 449
   - Generate a culturally appropriate name from that faction's language profile
   - Hard-code in the narrator persona string

---

## Open Questions

- **Copyright on Dunsany in UK/EU:** Dunsany died in 1957; under UK/EU
  rules (life + 70 years) his works are in copyright until 2028. If this
  project is used commercially or publicly, use only his clearly pre-1924
  works (*The Gods of Pegāna* 1905, *A Dreamer's Tales* 1910, *Fifty-One Tales*
  1915) which are unambiguously public domain everywhere. For private prototype
  use, the 1924 novel is fine in the US.

- **Retrieval granularity:** Five chunks per query may be too many for the
  context window if ai_summary is already large. May need to reduce to 3 chunks
  or truncate each chunk to 200 tokens for the prompt injection.

- **Multi-query blending:** If the summary has 8 distinct event types, running
  8 retrieval queries produces up to 40 chunks before deduplication. A smarter
  approach: run a single combined query per *narrative phase* (early / middle /
  late), keeping total retrieved passages to 6–9.

- **Narrator voice consistency:** The Elagos persona works best when the
  narrator can refer to Elagos itself — but Elagos appears in the world only as
  a future arrival point for the Elagosi civilization. The narrator should be
  aware that Elagos in Year 449 is a small port under uncertain control, and
  write from that vantage accordingly.
