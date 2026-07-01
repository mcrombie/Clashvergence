# Living Chronicle Plan

## Feature Goal

Every 25 turns during simulation, generate a short narrative chronicle entry using the LLM. Entries accumulate into a single "living chronicle" document. Each entry is written from the perspective of a narrator who is a contemporary of *that epoch* — they do not know what comes next, and their cultural voice reflects who is dominant, what religion holds sway, and how much distance separates them from the founding culture. The result is a document that reads as the world's own historical tradition, with the writing style visibly shifting across generations.

This is distinct from the existing end-of-run `interpretive_narrative.txt`, which is retrospective and unified. The living chronicle is prospective, plural, and shows cultural drift *as it happens*.

---

## Core Design Decisions

### 1. The Narrator Is Derived, Not Fixed

The current system uses one fixed narrator: "Boueni-descended remnant, Year 449." The living chronicle needs a *different narrator persona per epoch*, synthesised from the world state at that turn. This is the central design challenge.

**Narrator identity factors (computable from world state):**

| Signal | What it changes in narrator voice |
|---|---|
| Who owns the Grassic Kin homeland region(s) | Whether narrator is insider/exile/successor |
| Dominant religion at the core | Sacred references, what oaths narrator swears by |
| Primary ethnicity of dominant faction | Language roots, place-name relationship (reverent vs. foreign) |
| Whether founding faction (Grassic Kin) still exists | Nostalgic elegy vs. triumphalist chronicle vs. pragmatic heir |
| Administrative overextension of dominant power | Whether narrator writes from a stable center or a crumbling margin |
| Number of secession events in the epoch | Whether this era feels fragmenting or consolidating |

**Output:** A `narrator_origin_context` string computed per epoch, injected into the system prompt in place of the hardcoded Boueni one.

**Example narrator shift across epochs:**
- Turn 25: "I write among the Grassic Kin elders, where the names of ridges are still fixed by the founders' speech..."
- Turn 75: "I write in the court of the Riesov rising, where the old Grassic forms survive in ceremony but the tallies are kept in a newer hand..."
- Turn 150: "I write from a border town whose grandfather served three masters in one lifetime, and who keeps accounts for a fourth..."

---

### 2. Each Entry Is Epoch-Scoped, Not Full-History

The narrator at turn 50 must not know about events at turn 100. The epoch summary passed to the LLM should contain:

- Only events from the current epoch window (turns `N−24` to `N`)
- Cumulative world state *as of turn N* (faction standings, region ownership, religion map)
- A brief "prior chronicle digest" — one or two sentences summarising what the previous entries established, without revealing future events

This "prior digest" is extracted from the last entry's closing paragraph (or generated as a summary sentence), giving the narrator a sense of inherited tradition without full hindsight.

---

### 3. Entry Length and Tone

- **Length:** 4–8 paragraphs (~600–1100 words per entry), much shorter than the end-of-run narrative
- **Tone:** shifts across epochs per cultural drift (see narrator derivation above)
- **Constraint:** narrator can only reference events and factions they plausibly know about — no anachronistic knowledge

The LLM system prompt should be parameterised so the narrator's emotional register is set by a computed `narrator_disposition` enum:

| Disposition | Trigger | Voice quality |
|---|---|---|
| `founding` | Turn ≤ 50, original faction dominant | Confident, naming things for the first time |
| `consolidating` | Dominant faction expanding, low unrest | Orderly, administrative, lists succession clearly |
| `embattled` | High unrest / active war in epoch | Terse, oblique, names enemies with care |
| `elegiac` | Founding faction lost or diminished | Mourning present tense, old names as relics |
| `syncretic` | New dominant faction, mixed ethnicity | Bridging voice, explains old terms to new readers |
| `fragmenting` | Multiple secessions in epoch | Unreliable narrator, hedges which name is correct |

---

### 4. RAG Per Epoch

The existing RAG system retrieves style passages from the Herodotus and Dunsany corpus using queries built from the AI summary. For the living chronicle:

- Build generation queries from the **epoch slice** only (not full-run summary)
- Add a query component derived from `narrator_disposition` — e.g., `elegiac` biases toward Dunsany's elegiac mythic register; `consolidating` biases toward Herodotus's documentary annalistic register
- Retrieve 5–7 passages per epoch (fewer than the 9 used end-of-run, since entries are shorter)

---

### 5. Chronicle Accumulation

Each epoch entry is appended to a single `living_chronicle.txt` file in the run's output directory. Format:

```
═══════════════════════════════════════════
THE GRASSIC ANNALS  ·  Years 1–25
[computed narrator byline]
═══════════════════════════════════════════

[entry prose]


═══════════════════════════════════════════
THE RIESOV MEMORY  ·  Years 26–50
[computed narrator byline]
═══════════════════════════════════════════

[entry prose]
```

The section heading ("THE GRASSIC ANNALS", "THE RIESOV MEMORY") is derived from the dominant faction's name and the current tradition name (from `world.calendar` or equivalent). This makes the heading itself a cultural artifact — a faction that conquers changes the name of the chronicle tradition.

---

## Architecture

### New Components

**`src/living_chronicle.py`** — central module

| Function | Purpose |
|---|---|
| `compute_epoch_narrator(world, turn)` | Derives narrator identity, disposition, and byline from world state |
| `build_epoch_summary(world, turn_start, turn_end)` | Slices `world.events` and `world.metrics` for the epoch; builds structured JSON analogous to `build_ai_interpretation_summary()` but scoped |
| `build_epoch_rag_queries(epoch_summary, narrator_disposition)` | Adapts `build_generation_queries()` for short-form epoch context |
| `generate_epoch_entry(epoch_summary, narrator_context, rag_passages)` | LLM call; returns prose string |
| `append_chronicle_entry(run_dir, entry_text, heading)` | Writes entry to `living_chronicle.txt` with section separator |
| `get_prior_digest(run_dir)` | Extracts closing sentence from last chronicle entry to pass as inherited tradition |

### Modified Components

**`main.py`**

In the simulation turn loop, add a check after each turn completes:

```python
if world.turn > 0 and world.turn % 25 == 0:
    maybe_generate_chronicle_epoch(world, config, run_dir)
```

The function `maybe_generate_chronicle_epoch()` calls the living chronicle pipeline if narrative generation is enabled in config. It should be non-blocking if possible (queue for post-turn write) or accept a flag to skip during fast runs.

**`src/ai_interpretation.py`**

Extract the narrator persona building logic from `BOUENI_REMNANT_NARRATOR_SYSTEM_PROMPT` into a parameterised function `build_narrator_system_prompt(narrator_context, rag_passages, disposition)` so it can be called with computed narrator context rather than the hardcoded Boueni one.

**`src/narrative_rag.py`**

Add an `epoch_mode` parameter to `build_generation_queries()` that caps query count at 6 and skips full-run queries (phase summaries, faction epilogues) in favour of epoch-local queries (recent turning points, active rivalries, current religion state).

### Config Additions (`src/config.py`)

```python
CHRONICLE_EPOCH_INTERVAL = 25        # turns between chronicle entries
CHRONICLE_ENABLED = True             # can disable for fast/test runs
CHRONICLE_ENTRY_MAX_TOKENS = 1400    # shorter than end-of-run 4200
CHRONICLE_RAG_PASSAGES = 6
CHRONICLE_OUTPUT_FILE = "living_chronicle.txt"
```

---

## Narrator Derivation Logic (`compute_epoch_narrator`)

```
1. Identify dominant_faction: faction with most regions at world.turn
2. Identify homeland_faction: faction that owns the Grassic founding region(s)
3. founding_still_dominant = (homeland_faction == original Grassic Kin)
4. Compute disposition:
   - Count secession events in epoch → if ≥ 3: fragmenting
   - Else if founding_still_dominant and turn ≤ 50: founding
   - Else if dominant_faction.unrest_level high: embattled
   - Else if dominant_faction != previous dominant_faction: syncretic
   - Else if founding faction eliminated this epoch: elegiac
   - Else: consolidating
5. Derive narrator_locale: dominant_faction's capital or largest region
6. Derive narrator_speech_note: reference to language ancestry
   - If ethnic composition of locale is >70% original ethnicity: "the old stems are still heard here"
   - If mixed: "where two speech-forms compete at the market"
   - If replacement complete: "where the old names survive only in ritual"
7. Compose narrator_origin_context string from above
8. Derive chronicle_tradition_name from dominant_faction + world calendar
9. Return EpochNarrator(disposition, origin_context, byline, tradition_name)
```

---

## Epoch Summary Structure

Analogous to `build_ai_interpretation_summary()` but scoped to the epoch slice:

```json
{
  "epoch_years": "26–50",
  "epoch_theme": "computed from dominant event types",
  "world_state_at_epoch_end": {
    "dominant_faction": "...",
    "faction_standings": [...],
    "active_religions": [...],
    "active_rivalries": [...]
  },
  "epoch_events": [...],          // all events in turn window
  "epoch_turning_points": [...],  // top 3 by magnitude
  "epoch_secessions": [...],
  "epoch_successions": [...],
  "epoch_religious_events": [...],
  "prior_chronicle_digest": "...", // closing line of previous entry
  "narrator_context": {...}        // output of compute_epoch_narrator
}
```

---

## Output Files

Per run, in `reports/runs/<run_id>/`:

| File | Contents |
|---|---|
| `living_chronicle.txt` | Accumulating prose entries, one per epoch |
| `living_chronicle_metadata.json` | Per-epoch narrator disposition, dominant faction, turn range — for inspection/debugging |

The existing `interpretive_narrative.txt` is unchanged. The two documents complement each other: the living chronicle is the world's own tradition-in-progress; the interpretive narrative is the retrospective scholarly reading of the completed age.

---

## Open Questions

1. **LLM cost per run.** At 25-turn intervals over a 450-turn run, that is 18 LLM calls. At 1400 max tokens each, roughly 25,200 output tokens total per run. Acceptable? Or should interval be configurable (50 turns for cost-sensitive runs)?

2. **Prior digest injection.** Should the prior digest be extracted automatically from the previous entry's last paragraph, or should the LLM be asked to produce an explicit "handoff sentence" at the end of each entry for the next narrator to inherit?

3. **Section heading language.** Should the chronicle tradition name be translated into a quasi-fictional register ("THE RIESOV MEMORY", "THE ANNALS OF THE IZOL CORRIDOR") or kept neutral ("Chronicle — Years 26–50, Riesov Rising dominant")?

4. **Narrator continuity across disposition changes.** If turn 50 is `elegiac` and turn 75 is `syncretic`, should the turn 75 narrator explicitly reference the previous tradition ("the Boueni mourners who kept this record before us") or begin fresh? The elegiac/syncretic pair is the most dramatically interesting case.

5. **Integration with existing live lore.** `src/live_lore.py` already updates per-turn HTML with a deterministic chronicle. Should the living chronicle entries be embedded in that HTML view (replacing deterministic text with LLM text at epoch boundaries), or remain separate files only?
