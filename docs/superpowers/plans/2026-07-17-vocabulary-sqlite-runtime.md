# Read-Only Vocabulary SQLite Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile the reviewed 100,000-lesson index into a deterministic SQLite resource and make Today, Review, Practice Center, and My use bounded read-only queries while all SwiftData learning progress remains attached to stable lesson IDs.

**Architecture:** Add one Python standard-library compiler and one concrete Swift `VocabularyContentStore`. The store loads lightweight index rows and bounded full DTO pools; existing pure services continue to select, schedule, and calculate progress without owning SQL. Xcode generates the database as a derived App resource and no longer bundles `VocabularySeed.json`.

**Tech Stack:** Python 3 `sqlite3`, Swift 6, system `SQLite3`, SwiftUI, SwiftData, XCTest, Xcode build phases, iOS 17+.

## Global Constraints

- The App remains fully offline and read-only with respect to vocabulary content.
- SwiftData remains the only user-progress store and writer.
- Preserve every stable lesson ID.
- Bundle `VocabularyContent.sqlite` and `ThirdPartyNotices.txt`; do not bundle `VocabularySeed.json`, source, review, report, manifest, or provenance data.
- Use native SQLite only; add no package or repository abstraction.
- Do not decode all 100,000 rich lesson DTOs at launch.
- Keep daily selection and review scheduling pure.
- Keep the existing `TabView` and `.tabBarMinimizeBehavior(.never)`.
- Content failure is explicit and localized; never silently show a partial bank.
- Run TDD and `git diff --check` before every commit.

---

## File Map

- `tools/build_vocabulary_database.py`: validate the reviewed index and atomically compile deterministic SQLite.
- `tools/test_build_vocabulary_database.py`: schema, count, integrity, determinism, and atomic-failure tests.
- `Vocaby/Models/VocabularyModels.swift`: add lightweight `VocabularyLessonIndex` and content metadata DTOs without duplicating rich content fields.
- `Vocaby/Services/VocabularyContentStore.swift`: concrete read-only SQLite access and DTO reconstruction.
- `VocabyTests/VocabularyContentStoreTests.swift`: real temporary SQLite fixture tests.
- `Vocaby/Services/DailySelectionService.swift`: consume lightweight index items.
- `VocabyTests/DailySelectionServiceTests.swift`: preserve current selection behavior with index fixtures.
- `Vocaby/Services/LibraryService.swift`: combine database totals with SwiftData learned IDs and accept bounded loaded items.
- `VocabyTests/LibraryServiceTests.swift`: level-count and learned/saved behavior.
- `Vocaby/Services/ReviewQueueService.swift`: preserve due-order filtering on bounded loaded rows.
- `Vocaby/Features/Today/TodayView.swift`: select from lightweight index and load bounded practice content.
- `Vocaby/Features/Review/ReviewView.swift`: fetch only due rows plus bounded distractors.
- `Vocaby/Features/Practice/PracticeView.swift`: receive selected/bounded candidate pools instead of the full bank.
- `Vocaby/Features/Library/LibraryView.swift`: fetch learned/saved/deep-linked IDs only and show SQLite totals.
- `Vocaby/Resources/Localizable.xcstrings`: explicit unavailable-content strings in English and zh-Hant.
- `VocabyTests/LocalizationCoverageTests.swift`: localization contract for the error state.
- `VocabyTests/VocabularySeedValidationTests.swift`: replace JSON resource assertions with SQLite full-bank validation.
- `Vocaby.xcodeproj/project.pbxproj`: link system SQLite, add source/test files, generate the database resource, and remove the JSON seed resource.
- `tools/test_app_configuration.py`: prove bundle-resource exclusions and generation command.

---

### Task 1: Build Deterministic SQLite from the Reviewed Index

**Files:**
- Create: `tools/build_vocabulary_database.py`
- Create: `tools/test_build_vocabulary_database.py`

**Interfaces:**
- Produces: `build_database(index_path: Path, output_path: Path, expected_count: int) -> dict[str, object]`.
- CLI: `python3 tools/build_vocabulary_database.py --index PATH --output PATH --expected-count 100000`.

- [ ] **Step 1: Write the failing schema/determinism test**

```python
class VocabularyDatabaseTests(unittest.TestCase):
    def test_build_database_is_deterministic_and_complete(self):
        index = self.make_review_index(item_count=3)
        first = self.root / "first.sqlite"
        second = self.root / "second.sqlite"

        first_result = build_vocabulary_database.build_database(index, first, 3)
        second_result = build_vocabulary_database.build_database(index, second, 3)

        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(first_result["items"], 3)
        with sqlite3.connect(first) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertEqual(
                tables,
                {"metadata", "lessons", "senses", "pronunciations"},
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM lessons").fetchone()[0],
                3,
            )
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
```

Add tests for tampered shard hash, duplicate lesson/sense/pronunciation ID, invalid foreign reference, wrong count, and preserving an existing output after failure.

- [ ] **Step 2: Verify RED**

```sh
python3 -B -m unittest tools.test_build_vocabulary_database
```

Expected: import failure because `build_vocabulary_database.py` does not exist.

- [ ] **Step 3: Implement the fixed schema**

Use:

```sql
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE lessons (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL CHECK(level IN ('basic','intermediate','advanced')),
    cefr TEXT NOT NULL CHECK(cefr IN ('A1','A2','B1','B2','C1','C2')),
    sort_order INTEGER NOT NULL,
    content_language_code TEXT NOT NULL,
    support_language_codes TEXT NOT NULL,
    plain_expression TEXT NOT NULL,
    upgraded_expression TEXT NOT NULL,
    normalized_expression TEXT NOT NULL UNIQUE,
    primary_sense_id TEXT NOT NULL,
    quiz_json TEXT NOT NULL,
    UNIQUE(level, sort_order)
) WITHOUT ROWID;

CREATE TABLE senses (
    lesson_id TEXT NOT NULL REFERENCES lessons(id),
    id TEXT NOT NULL,
    position INTEGER NOT NULL,
    part_of_speech TEXT NOT NULL,
    meaning_en TEXT NOT NULL,
    meaning_zh_hant TEXT NOT NULL,
    example_en TEXT NOT NULL,
    example_zh_hant TEXT NOT NULL,
    pronunciation_ids_json TEXT NOT NULL,
    PRIMARY KEY (lesson_id, id),
    UNIQUE (lesson_id, position)
) WITHOUT ROWID;

CREATE TABLE pronunciations (
    lesson_id TEXT NOT NULL REFERENCES lessons(id),
    id TEXT NOT NULL,
    position INTEGER NOT NULL,
    ipa TEXT NOT NULL,
    speech_locale TEXT NOT NULL,
    region TEXT,
    PRIMARY KEY (lesson_id, id),
    UNIQUE (lesson_id, position)
) WITHOUT ROWID;

CREATE INDEX lessons_level_sort
ON lessons(level, sort_order);
CREATE INDEX senses_lesson_position
ON senses(lesson_id, position);
CREATE INDEX pronunciations_lesson_position
ON pronunciations(lesson_id, position);
```

- [ ] **Step 4: Make the file deterministic and atomic**

Set `page_size=4096`, `journal_mode=OFF`, `synchronous=OFF`,
`auto_vacuum=NONE`, and `foreign_keys=ON` before creating tables. Insert
lessons and children in reviewed-index order, serialize compact JSON with
`sort_keys=True`, run `foreign_key_check`, `integrity_check`, and `VACUUM`,
close the connection, then use `os.replace(temporary, output_path)`.

- [ ] **Step 5: Run tests and commit**

```sh
python3 -B -m unittest tools.test_build_vocabulary_database
git add tools/build_vocabulary_database.py tools/test_build_vocabulary_database.py
git diff --cached --check
git commit -m "feat: compile reviewed vocabulary SQLite"
git push origin HEAD
```

---

### Task 2: Add the Concrete Swift Read-Only Content Store

**Files:**
- Modify: `Vocaby/Models/VocabularyModels.swift`
- Create: `Vocaby/Services/VocabularyContentStore.swift`
- Create: `VocabyTests/VocabularyContentStoreTests.swift`

**Interfaces:**
- Produces: `VocabularyContentMetadata`, `VocabularyLessonIndex`, and `VocabularyContentStore`.

- [ ] **Step 1: Add lightweight DTOs**

```swift
struct VocabularyContentMetadata: Equatable {
    let schemaVersion: Int
    let bankVersion: String
    let itemCount: Int
    let reviewedIndexSHA256: String
}

struct VocabularyLessonIndex: Identifiable, Equatable {
    let id: String
    let level: VocabularyLevel
    let sortOrder: Int
    let contentLanguageCode: String
    let supportLanguageCodes: [String]
}
```

- [ ] **Step 2: Write failing store tests**

Cover:

```swift
func testStoreLoadsMetadataIndexAndRequestedItemsOnly() throws {
    let store = try VocabularyContentStore(url: fixtureURL)

    XCTAssertEqual(try store.metadata().itemCount, 3)
    XCTAssertEqual(try store.indexItems().map(\.id), ["basic-1", "mid-1", "advanced-1"])
    XCTAssertEqual(
        try store.items(ids: ["mid-1"]).map(\.id),
        ["mid-1"]
    )
}

func testStoreRejectsWrongSchemaVersion() throws {
    try setMetadata("schemaVersion", to: "999")
    XCTAssertThrowsError(try VocabularyContentStore(url: fixtureURL))
}
```

Add invalid quiz JSON, missing sense, dangling pronunciation reference, duplicate requested IDs, and requested-order tests.

- [ ] **Step 3: Verify RED**

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -only-testing:VocabyTests/VocabularyContentStoreTests \
  CODE_SIGNING_ALLOWED=NO
```

Expected: build failure because the store and DTOs do not exist.

- [ ] **Step 4: Implement one concrete store**

```swift
final class VocabularyContentStore {
    private var database: OpaquePointer?

    convenience init(bundle: Bundle = Bundle(for: BundleToken.self)) throws {
        guard let url = bundle.url(
            forResource: "VocabularyContent",
            withExtension: "sqlite"
        ) else {
            throw VocabularyContentStoreError.missingResource
        }
        try self.init(url: url)
    }

    init(url: URL) throws {
        guard sqlite3_open_v2(
            url.path,
            &database,
            SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX,
            nil
        ) == SQLITE_OK else {
            throw VocabularyContentStoreError.openFailed
        }
        try validateMetadata()
    }

    deinit {
        sqlite3_close(database)
    }

    func metadata() throws -> VocabularyContentMetadata
    func indexItems() throws -> [VocabularyLessonIndex]
    func levelCounts() throws -> [VocabularyLevel: Int]
    func items(ids: [String]) throws -> [VocabularySeedItem]
    func items(
        level: VocabularyLevel,
        including preferredIDs: [String],
        limit: Int
    ) throws -> [VocabularySeedItem]
}
```

Use prepared statements and explicit column decoding. Reject invalid enum/raw
values, absent children, invalid primary sense, malformed JSON, and unknown
pronunciation references.

- [ ] **Step 5: Run focused tests and commit**

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -only-testing:VocabyTests/VocabularyContentStoreTests \
  CODE_SIGNING_ALLOWED=NO
git add Vocaby/Models/VocabularyModels.swift \
  Vocaby/Services/VocabularyContentStore.swift \
  VocabyTests/VocabularyContentStoreTests.swift \
  Vocaby.xcodeproj/project.pbxproj
git diff --cached --check
git commit -m "feat: read vocabulary from bundled SQLite"
git push origin HEAD
```

---

### Task 3: Keep Daily Selection Pure on Lightweight Index Rows

**Files:**
- Modify: `Vocaby/Services/DailySelectionService.swift`
- Modify: `VocabyTests/DailySelectionServiceTests.swift`

**Interfaces:**
- Changes `selectItems(from: [VocabularySeedItem], ...)` to `selectItems(from: [VocabularyLessonIndex], ...)`.

- [ ] **Step 1: Convert the tests to index fixtures**

Add:

```swift
private func index(
    id: String,
    level: VocabularyLevel,
    sortOrder: Int
) -> VocabularyLessonIndex {
    VocabularyLessonIndex(
        id: id,
        level: level,
        sortOrder: sortOrder,
        contentLanguageCode: "en",
        supportLanguageCodes: ["zh-Hant"]
    )
}
```

Retain every existing selection expectation.

- [ ] **Step 2: Verify RED**

Run the existing DailySelectionService test target; expect type mismatch until the service signature changes.

- [ ] **Step 3: Change only the input type**

```swift
func selectItems(
    from indexItems: [VocabularyLessonIndex],
    selectedLevel: VocabularyLevel,
    contentLanguageCode: String,
    supportLanguageCode: String,
    firstSeenItemIDs: Set<String>,
    dueReviewItemIDs: [String],
    targetCount: Int = 10
) -> DailySelectionResult
```

Keep filtering, sort, unseen-first, due-fill, and status logic unchanged.

- [ ] **Step 4: Run tests and commit**

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -only-testing:VocabyTests/DailySelectionServiceTests \
  CODE_SIGNING_ALLOWED=NO
git add Vocaby/Services/DailySelectionService.swift \
  VocabyTests/DailySelectionServiceTests.swift
git diff --cached --check
git commit -m "refactor: select daily lessons from content index"
git push origin HEAD
```

---

### Task 4: Load Bounded Today and Practice Content

**Files:**
- Modify: `Vocaby/Features/Today/TodayView.swift`
- Modify: `Vocaby/Features/Practice/PracticeView.swift`
- Modify: `VocabyTests/QuizEngineTests.swift`

**Interfaces:**
- Today keeps `@State private var lessonIndex: [VocabularyLessonIndex] = []`.
- Practice views receive only selected lessons plus a bounded same-level candidate pool.

- [ ] **Step 1: Add a bounded-pool regression test**

```swift
func testDailyPracticePlanUsesBoundedCandidatePool() {
    let selected = makeItems(count: 10)
    let candidates = makeItems(count: 64)

    let plan = DailyPracticePlan(
        session: makeSession(ids: selected.map(\.id)),
        selectedItems: selected,
        candidateItems: candidates,
        supportLanguageCode: "zh-Hant"
    )

    XCTAssertEqual(plan.quizQuestions.count, 10)
    XCTAssertLessThanOrEqual(candidates.count, 64)
}
```

- [ ] **Step 2: Verify RED**

Run `VocabyTests/QuizEngineTests`; expect initializer mismatch.

- [ ] **Step 3: Split selected and candidate inputs**

```swift
init(
    session: DailySession,
    selectedItems: [VocabularySeedItem],
    candidateItems: [VocabularySeedItem],
    supportLanguageCode: String
)
```

Build `seedByID` from `selectedItems`; pass `candidateItems` only to
`QuizEngine.makeQuestions`.

- [ ] **Step 4: Replace Today's full seed state**

Use:

```swift
@State private var lessonIndex: [VocabularyLessonIndex] = []
@State private var loadedItems: [VocabularySeedItem] = []
private let contentStore = try? VocabularyContentStore()
```

`loadIndexIfNeeded` loads only index rows. After daily selection, fetch the ten selected IDs and a same-level pool capped at 64. Existing session IDs are fetched directly.

- [ ] **Step 5: Keep Practice Center bounded**

Before opening Practice Center, ask the store for at most 200 same-level lessons while including learned IDs selected for the run. Pass that bounded array to the existing `PracticeCenterPlan`; do not load all 100,000 rich DTOs.

- [ ] **Step 6: Run practice/daily tests and commit**

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -only-testing:VocabyTests/DailySelectionServiceTests \
  -only-testing:VocabyTests/QuizEngineTests \
  CODE_SIGNING_ALLOWED=NO
git add Vocaby/Features/Today/TodayView.swift \
  Vocaby/Features/Practice/PracticeView.swift \
  VocabyTests/QuizEngineTests.swift
git diff --cached --check
git commit -m "feat: bound vocabulary practice queries"
git push origin HEAD
```

---

### Task 5: Load Only Due, Learned, Saved, and Deep-Linked Content

**Files:**
- Modify: `Vocaby/Features/Review/ReviewView.swift`
- Modify: `Vocaby/Features/Library/LibraryView.swift`
- Modify: `Vocaby/Services/LibraryService.swift`
- Modify: `Vocaby/Services/ReviewQueueService.swift`
- Modify: `VocabyTests/LibraryServiceTests.swift`
- Modify: `VocabyTests/ReviewQueueServiceTests.swift`

**Interfaces:**
- Library summary consumes database totals and lightweight index rows.
- Review queue consumes already loaded due items in due order.

- [ ] **Step 1: Add level-total tests**

```swift
func testLevelSummariesUseDatabaseTotalsAndLearnedIndex() {
    let totals: [VocabularyLevel: Int] = [
        .basic: 10,
        .intermediate: 20,
        .advanced: 70,
    ]
    let index = [
        index(id: "b", level: .basic),
        index(id: "a", level: .advanced),
    ]

    let summaries = LibraryService().levelSummaries(
        totals: totals,
        indexItems: index,
        learnedItemIDs: ["b", "a"]
    )

    XCTAssertEqual(summaries.map(\.totalCount), [10, 20, 70])
    XCTAssertEqual(summaries.map(\.learnedCount), [1, 0, 1])
}
```

- [ ] **Step 2: Verify RED**

Run Library and ReviewQueue tests; expect signature failures.

- [ ] **Step 3: Change LibraryService to bounded inputs**

```swift
func levelSummaries(
    totals: [VocabularyLevel: Int],
    indexItems: [VocabularyLessonIndex],
    learnedItemIDs: Set<String>
) -> [LibraryLevelSummary]

func items(
    from loadedItems: [VocabularySeedItem],
    progressRows: [WordProgress],
    quizResults: [QuizResult],
    scope: LibraryScope,
    query: String
) -> [LibraryListItem]
```

- [ ] **Step 4: Fetch only relevant Library IDs**

In `refreshLibrary`, collect learned IDs from quiz results, saved IDs from progress, and the pending deep-link ID. Fetch their full rows in one store call. Level totals come from `levelCounts()`; no rich whole-bank array remains.

- [ ] **Step 5: Fetch only due Review IDs**

Use the scheduler's limited due rows, fetch those IDs from the store, preserve scheduler order through `ReviewQueueService`, and fetch a same-level candidate pool capped at 64 for quiz distractors.

- [ ] **Step 6: Run focused tests and commit**

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -only-testing:VocabyTests/LibraryServiceTests \
  -only-testing:VocabyTests/ReviewQueueServiceTests \
  CODE_SIGNING_ALLOWED=NO
git add Vocaby/Features/Review/ReviewView.swift \
  Vocaby/Features/Library/LibraryView.swift \
  Vocaby/Services/LibraryService.swift \
  Vocaby/Services/ReviewQueueService.swift \
  VocabyTests/LibraryServiceTests.swift \
  VocabyTests/ReviewQueueServiceTests.swift
git diff --cached --check
git commit -m "feat: query bounded review and library content"
git push origin HEAD
```

---

### Task 6: Generate and Bundle SQLite, Remove the JSON Seed

**Files:**
- Modify: `Vocaby.xcodeproj/project.pbxproj`
- Modify: `tools/test_app_configuration.py`
- Modify: `VocabyTests/VocabularySeedValidationTests.swift`
- Move: `Vocaby/Resources/VocabularySeed.json` to `Content/Baselines/VocabularySeed-14064.json`

**Interfaces:**
- Produces App resource `VocabularyContent.sqlite` during build.

- [ ] **Step 1: Add failing project contract assertions**

```python
def test_app_build_generates_only_reviewed_vocabulary_database(self):
    project = (ROOT / "Vocaby.xcodeproj/project.pbxproj").read_text()
    self.assertIn("build_vocabulary_database.py", project)
    self.assertIn("VocabularyContent.sqlite", project)
    self.assertNotIn("VocabularySeed.json in Resources", project)
    self.assertNotIn("Content/Reviews", project)
```

- [ ] **Step 2: Verify RED**

```sh
python3 -B -m unittest tools.test_app_configuration
```

Expected: failure because the project still bundles `VocabularySeed.json`.

- [ ] **Step 3: Add one declared-output build phase**

The phase runs:

```sh
/usr/bin/python3 "${SRCROOT}/tools/build_vocabulary_database.py" \
  --output "${TARGET_BUILD_DIR}/${UNLOCALIZED_RESOURCES_FOLDER_PATH}/VocabularyContent.sqlite" \
  --expected-count 100000
```

When `--index` is omitted, the compiler resolves
`Content/Reviews/vocabulary-100k/index.json` relative to its own repository
root. Declare only the compiler as the build phase input and the bundled
database path as output. Add `libsqlite3.tbd` to the App target. Remove both
`VocabularySeed.json in Resources` entries and its file reference. Do not add
`Content/Reviews` to a group or resource phase.

- [ ] **Step 4: Replace seed validation tests**

`VocabularySeedValidationTests` opens the bundled database through
`VocabularyContentStore`, asserts metadata count 100,000, then pages through
index IDs and validates rich rows in bounded chunks of 500.

- [ ] **Step 5: Run project and bundle tests**

```sh
python3 -B -m unittest tools.test_app_configuration \
  tools.test_build_vocabulary_database
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  CODE_SIGNING_ALLOWED=NO
```

- [ ] **Step 6: Commit and push**

```sh
git add Vocaby.xcodeproj/project.pbxproj \
  tools/test_app_configuration.py \
  VocabyTests/VocabularySeedValidationTests.swift \
  Content/Baselines/VocabularySeed-14064.json
git add -u Vocaby/Resources/VocabularySeed.json
git diff --cached --check
git commit -m "build: bundle reviewed vocabulary SQLite"
git push origin HEAD
```

---

### Task 7: Localized Failure State and Full Runtime Verification

**Files:**
- Modify: `Vocaby/Resources/Localizable.xcstrings`
- Modify: `VocabyTests/LocalizationCoverageTests.swift`
- Modify: `docs/manual-verification.md`

**Interfaces:**
- Produces localized `vocabulary.content.unavailable` and accessibility-safe error presentation.

- [ ] **Step 1: Add localization coverage assertions**

Require nonempty English and zh-Hant values for `vocabulary.content.unavailable` and use the key in Today, Review, and My catch paths.

- [ ] **Step 2: Run localization and full Swift tests**

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  CODE_SIGNING_ALLOWED=NO
```

Expected: all Swift tests pass.

- [ ] **Step 3: Run a Release build and inspect resources**

```sh
rm -rf /tmp/Vocaby-100k-Release
xcodebuild build \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/Vocaby-100k-Release \
  CODE_SIGNING_ALLOWED=NO
find /tmp/Vocaby-100k-Release/Build/Products/Release-iphoneos/Vocaby.app \
  -maxdepth 2 -type f | sort
```

Expected: bundle contains `VocabularyContent.sqlite` and
`ThirdPartyNotices.txt`; it contains no `VocabularySeed.json`, source,
review, report, manifest, or provenance file.

- [ ] **Step 4: Run real-device performance and UI checks**

Measure cold metadata open under one second, Today 10-row fetch under 200 ms,
My first-page/count queries under 200 ms, and confirm no whole-bank rich DTO
allocation in Instruments. Verify zh-Hant/English accessibility Dynamic Type
and the non-minimizing tab bar.

- [ ] **Step 5: Commit and push verification updates**

```sh
git add Vocaby/Resources/Localizable.xcstrings \
  VocabyTests/LocalizationCoverageTests.swift docs/manual-verification.md
git diff --cached --check
git commit -m "test: verify 100k vocabulary runtime"
git push origin HEAD
```
