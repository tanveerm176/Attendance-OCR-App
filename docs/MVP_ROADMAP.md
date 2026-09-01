# Attendance OCR App — MVP Roadmap

This document lays out every remaining step between the current state of the
repository and a finished, working MVP. It assumes the project structure
already documented in `PROJECT_STRUCTURE.md`, and it does **not** ask you to
rename or rewrite any file that already contains working logic
(`ingestion.py`, `table_detection.py`, `img_cropping.py`, `ocr.py`).

Steps are ordered by dependency — each step assumes the ones above it are
done. Where a step has sub-parts, they're listed in the order they should be
tackled.

---

## Where things stand right now

- `ocr_pipeline/ingestion.py` — done (PDF → RGB image render)
- `ocr_pipeline/table_detection.py` — done (vertical/horizontal kernel line detection)
- `ocr_pipeline/img_cropping.py` — done (validated crop helpers)
- `ocr_pipeline/ocr.py` — done (Tesseract cell OCR)
- `ocr_pipeline/classification.py` — **in progress** (HSV attendance classification)
- Everything below this line is still a placeholder or doesn't exist yet.

---

## Step 1 — Finish `ocr_pipeline/classification.py`

**What it does:** Takes a cropped "Sign In" cell image and returns `"Present"`
or `"Absent"` based on ink color, not OCR.

**Why this step is first:** It's a leaf function — it depends on nothing else
in the pipeline that isn't already built (`img_cropping.py` hands it a cell,
it hands back a string). It can be written and unit-tested in complete
isolation from every other undone piece.

**What "done" looks like:**
- Converts the cropped cell from RGB to HSV.
- Masks out background/paper pixels (low saturation, near-white).
- If there's enough saturated ink, classifies by hue: red-ish → `Absent`,
  blue-ish → `Present`.
- Falls back to a raw R−B channel-difference comparison when saturation is
  too low to trust hue (e.g., faint pen marks).
- Returns a plain string, `"Present"` or `"Absent"` — no dataclass yet, no
  side effects, no file I/O.

**What NOT to do here:** Don't reach for a class. This is a pure function —
image in, string out — exactly the kind of stateless transformation that
should stay a function per the earlier architecture discussion.

---

## Step 2 — Fill in `ocr_pipeline/reconciliation.py` (name cleaning + fuzzy match)

**What it does:** Two functions, both pure/stateless:
- `clean_ocr_name(raw_name: str) -> str` — regex-strips anything that isn't a
  letter, space, hyphen, or apostrophe. Cleans up OCR junk like
  `"Cintron, Dylan 7"` → `"Cintron, Dylan"`.
- `fuzzy_match_names(df: pd.DataFrame, roster: list[str], name_col: str) ->
  pd.DataFrame` — for each cleaned name, uses `rapidfuzz.process.extractOne`
  with `token_sort_ratio` against the roster, threshold 80, and appends
  `matched_name` and `match_score` columns.

**Naming note (carried over from the architecture discussion):** this file's
job — per its existing docstring — is *name-to-roster* matching, not the
later sheet-vs-database reconciliation stage. Keep it scoped to that. When
the sheet-vs-DB comparison gets built later, it goes in a separate,
distinctly-named module so the two don't collide.

**Dependency:** None of the pipeline's other unfinished pieces. Can be built
and tested independently, same as Step 1.

---

## Step 3 — Write `ocr_pipeline/exceptions.py`

**What it does:** Defines a small, specific exception hierarchy instead of
letting the pipeline fail with generic `IndexError`/`KeyError` deep inside
list indexing.

**Minimum set for MVP:**
- `TableDetectionError` — raised when `table_detection.py` can't find the
  expected number of column/row lines (e.g., a scan too skewed or too faint
  to detect a full grid).
- `OCRExtractionError` — raised when a cell OCR result is empty or otherwise
  unusable.
- `NoMatchFoundError` — raised (or used to flag, not necessarily raise) when
  a fuzzy match score falls below threshold with no acceptable candidate.

**Why this comes before `pipeline.py`:** the orchestrator's job in Step 5 is
to call each stage and handle failure paths sensibly. It needs these
exception types to exist first, otherwise "handle failure sensibly" has
nothing concrete to catch.

**What NOT to do here:** Don't over-build this. Three exception classes,
each a one-line subclass of `Exception`, is enough for MVP. No custom
`__init__` logic, no error codes, no logging built into the exception itself
— that belongs in `reporting/logger.py`, called separately.

---

## Step 4 — Write `ocr_pipeline/models.py`

**What it does:** Defines the data shapes that flow through and out of the
pipeline, using `@dataclass`.

**Minimum set for MVP:**
```python
@dataclass
class AttendanceRecord:
    ocr_name: str
    matched_name: str
    match_score: float
    status: Literal["Present", "Absent"]
```

**What's deliberately left out for MVP:** `student_id` is not included yet.
The earlier architecture discussion flagged carrying resolved student IDs
(not just matched name strings) as the right long-term design — so fuzzy-match
errors don't silently look like reconciliation errors downstream — but that
only matters once there's an actual database to resolve IDs against. For
MVP, matching against a flat roster list, `matched_name` is the closest
identifier available. Add `student_id` when `db_cleaning.py` and real
database reconciliation are built.

**`ReconciliationResult` is also deferred.** It only makes sense once
there's a database to reconcile *against* — right now there's just a roster
list and a sign-in sheet, no independent source of truth to compare
attendance against. Building `ReconciliationResult` now would mean guessing
at its shape. Leave it out of MVP; it belongs to the post-MVP phase (see
"Explicitly out of scope" below).

---

## Step 5 — Extend `config.py` with `PipelineConfig`

**What it does:** Adds one typed dataclass that the orchestrator will use,
without touching whatever's already in `config.py` (DPI setting, optional
S3 bucket config, output directory).

```python
@dataclass
class PipelineConfig:
    roster: list[str]
    name_col_index: int = 2
    attendance_col_index: int = 5
    last_table_col_index: int = 5
    fuzzy_match_threshold: int = 80
    tesseract_config: str = "--oem 1 --psm 7"
```

**Where the roster list comes from:** this is the point where
`io/roster_input.py` becomes relevant — see Step 6. `PipelineConfig` just
needs *a* list of strings; it doesn't care whether that list came from a
`.txt` file, a `.csv`, or a hardcoded list during early testing.

---

## Step 6 — Fill in `io/roster_input.py`

**What it does:** Loads `data/student_roster.txt` into a plain
`list[str]`, with basic validation (non-empty, no duplicate blank lines,
stripped whitespace).

**Why now and not earlier:** `PipelineConfig` (Step 5) needs a roster list
to be constructed. This function is what produces that list from disk. It's
intentionally simple for MVP — no format auto-detection, no multiple-roster
support, just "read the one file, return clean strings."

---

## Step 7 — Fill in `io/excel_output.py`

**What it does:** Takes the final DataFrame (names, matched names, match
scores, attendance status, date) and writes it to an `.xlsx` file via
`df.to_excel()`.

**Minimum set for MVP:**
- One function, e.g. `export_attendance(df: pd.DataFrame, output_path:
  Path) -> None`.
- No formatting, conditional highlighting, or multi-sheet output yet — a
  clean single-sheet export is enough for MVP. Visual polish (e.g.,
  highlighting low-confidence matches in red) is a reasonable post-MVP
  addition, not a blocker.

---

## Step 8 — Write `ocr_pipeline/pipeline.py` (the `OCRPipeline` orchestrator)

This is the step that ties every finished module together. Do it in **two
passes**, per the "interface before implementation" principle from the
earlier discussion — don't wire in real calls on the first pass.

### Pass 1 — Skeleton with stub returns

Write `OCRPipeline.__init__` and `OCRPipeline.run()` with the correct method
signature and correct sequence of stage calls, but have each stage return a
hardcoded placeholder value instead of really calling into the module yet.
The goal of this pass is to confirm:
- `run()`'s signature is `run(self, pdf_path: Path) -> pd.DataFrame` — no
  more, no less.
- The exact shape handed from one stage to the next (e.g., does
  `table_detection` hand `img_cropping` a tuple of `(col_positions,
  row_positions)`? Does `ocr.py` expect a single cropped cell or a whole
  cropped column?).
- Every stage boundary that raises a question gets resolved on paper before
  any real logic is wired in.

### Pass 2 — Wire in real calls

Replace each stub with the actual call into the finished module:
1. `ingestion.pdf_to_image(pdf_path)` → RGB + grayscale image
2. `table_detection.get_vertical_line_positions(img_gray)` → column
   positions
3. Crop to first 5 columns using `img_cropping`
4. `table_detection.get_horizontal_line_positions(cropped_img)` → row
   positions
5. Loop rows: `ocr.tesseract_ocr()` on the name cell,
   `classification.classify_attendance()` on the attendance cell
6. Zip into a DataFrame
7. `reconciliation.clean_ocr_name()` + `reconciliation.fuzzy_match_names()`
8. Return the DataFrame — **do not** prompt for the date or write the Excel
   file inside `pipeline.py`. Both of those are `main.py`'s job (see Step
   9), so that Phase 2 (GUI) and Phase 3 (web) can call `run()` and supply
   the date a different way later, without touching pipeline code.

**Error handling:** wrap the table-detection step so that if the expected
number of columns/rows isn't found, it raises `TableDetectionError` (Step 3)
instead of letting a bare `IndexError` propagate from list indexing.

---

## Step 9 — Rewrite `main.py` to use `OCRPipeline`

**What changes:** The "documents the planned end-to-end batch workflow"
comment block gets replaced with real orchestration. The update-check call
to `updater.py` stays exactly where it is — this step doesn't touch that.

**Final shape of `main.py`:**
1. Parse CLI args (PDF path, optional output path) — same as the earlier
   `main.py` draft.
2. Call `updater.py`'s update check (unchanged).
3. Load roster via `io.roster_input`, build `PipelineConfig` (Step 5/6).
4. Instantiate `OCRPipeline(config)`, call `.run(pdf_path)`.
5. Prompt for the sheet date via CLI (`MM/DD/YYYY`, validated with
   `pd.to_datetime`) — this stays a manual prompt for MVP; automated date
   OCR is explicitly deferred (see below).
6. Insert the date into the returned DataFrame.
7. Call `io.excel_output.export_attendance()` to write the file.
8. Print a short summary via `reporting/summary.py`.

---

## Step 10 — Fill in `reporting/summary.py` and `reporting/logger.py`

**`summary.py`:** After export, print a short run summary — number of rows
processed, number of names matched above threshold vs. flagged low-
confidence, output file path. Plain print statements are enough for MVP; no
need for a formatted report yet.

**`logger.py`:** Basic logging of each run — timestamp, input PDF, output
path, any exceptions caught. Standard library `logging` module, writing to a
log file, is sufficient for MVP. No structured/JSON logging or log rotation
needed yet.

**Why these are last, not earlier:** both depend on the pipeline actually
producing a result to summarize/log. Building them earlier would mean
guessing at what data will be available to report on.

---

## Step 11 — Write/finish the test suite

Tests should be filled in alongside — or immediately after — the module
they cover, not all saved until the very end. Listed here as one step for
clarity, but in practice this runs in parallel with Steps 1–9.

- `tests/test_ingestion.py` — already exists; confirm it still passes.
- `tests/test_img_cropping.py` — already exists; confirm it still passes.
- `tests/test_table_detection.py` — already exists; confirm it still passes.
- `tests/test_ocr.py` — already exists; confirm it still passes.
- `tests/test_reconciliation.py` — fill in: test `clean_ocr_name` against a
  handful of known-messy OCR strings; test `fuzzy_match_names` against a
  small fake roster with known-correct matches.
- **New:** `tests/test_classification.py` — feed known red-ink and
  blue-ink cell crops, assert correct `Present`/`Absent` classification,
  including a low-saturation fallback case.
- **New:** `tests/test_pipeline.py` — integration test. Run
  `tests/sample_scans/sonyc-test.pdf` through `OCRPipeline.run()` end to
  end, assert the returned DataFrame has the right columns and a sane row
  count. This is the test that would have caught issues like the
  `cv2.dilate` bug discussed earlier, automatically, going forward.

---

## Step 12 — End-to-end manual validation

Before calling the MVP "done":
1. Run the real CLI (`main.py`) against `tests/sample_scans/sonyc-test.pdf`.
2. Manually check the output Excel file against the actual sign-in sheet —
   every name, every attendance mark, by eye.
3. Note any systematic misreads (a particular letter Tesseract confuses, a
   color-classification edge case) — these become either quick fixes now or
   documented known limitations for later.
4. Confirm the CLI date prompt correctly rejects malformed input and accepts
   valid `MM/DD/YYYY` dates.

**This step is the actual MVP finish line** — once a real scanned sheet goes
in and a correct, human-verified Excel file comes out, the MVP is complete.

---

## Explicitly out of scope for this MVP

These were discussed and deliberately deferred — listed here so nothing gets
mistaken for a missing MVP step:

- **`ocr_pipeline/deskew.py`** — implemented in the notebook but degrades
  OCR accuracy; not validated end-to-end. Stays a placeholder.
- **Automated date extraction** — stylized font + underline made OCR
  unreliable. MVP uses a CLI prompt instead.
- **Database reconciliation** (`db_cleaning.py`, a future
  `db_reconciliation.py`, and `ReconciliationResult`) — there's no database
  to reconcile against yet; this is a genuinely separate future stage, not
  part of matching names to the flat roster list.
- **`phase2-gui/`** — desktop GUI. Depends on `OCRPipeline.run()` existing
  as a clean callable (Step 8), which this MVP roadmap delivers, but
  building the GUI itself is Phase 2.
- **`phase3-web/`** — local web page. Same dependency, later phase.
- **AWS integration** — planned for the SA Associate cert learning track;
  `config.py`'s optional S3 bucket setting can stay unused/unconfigured for
  MVP.
- **CI/CD (GitHub Actions) and Docker** — valuable for the skill-building
  goal, but not required for a human to run `main.py` locally and get a
  correct Excel file out. Sequencing suggestion from earlier: finish the
  pipeline first, then Dockerfile, then CI YAML.
- **Excel output formatting/highlighting** — plain single-sheet export is
  enough; visual polish is a post-MVP nice-to-have.
