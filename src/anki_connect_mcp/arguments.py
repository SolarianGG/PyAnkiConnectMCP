"""Descriptions for the top-level arguments of every Anki-Connect method.

The bundled schema has no per-argument descriptions, and the model cannot follow
links to API_V1.md, so the conventions it needs are spelled out here. Tool names
are referenced in their MCP form (``collection_get``), as the model sees them.
"""

from __future__ import annotations

_DECK_REF = 'exactly one of {"id": "<deckId>"} or {"name": "<full deck name, e.g. Japanese::Verbs>"}'
_NOTE_TYPE_REF = 'exactly one of {"id": "<noteTypeId>"} or {"name": "<note type name, e.g. Basic>"}'
_PRESET_REF = 'exactly one of {"id": "<presetId>"} or {"name": "<preset name>"}'
_ID = "decimal string, e.g. \"1700000000001\""

# Arguments whose meaning does not depend on the method.
COMMON: dict[str, str] = {
    "session": (
        "Optional. Collection session ID: the `session` field returned by `collection_get`. "
        "Usually omit it — the server then uses the session current at the time of the call. "
        "Pass it to make the call fail with `staleSession` instead of acting on a different "
        "profile/collection than the one your IDs, cursors and tokens came from."
    ),
    "query": "Anki search query in browser syntax, e.g. `deck:Japanese tag:verb is:due`. An empty string matches everything.",
    "limit": "Page size, 1–1000 (default 100).",
    "cursor": (
        "Continuation token: `nextCursor` from the previous page of the same call. Omit for the "
        "first page. Repeat the same query, sort and limit; each cursor is single-use and expires "
        "after 10 minutes. `nextCursor: null` means there are no more pages."
    ),
    "sort": (
        'Optional browser-column sort, e.g. {"column": "noteFld", "direction": "ascending"} '
        "(`column` is an Anki browser column key such as noteFld, cardDue). Default: ascending ID order."
    ),
    "deck": f"Deck: {_DECK_REF}.",
    "decks": f"Decks, each {_DECK_REF}.",
    "noteType": f"Note type: {_NOTE_TYPE_REF}.",
    "noteTypes": f"Note types, each {_NOTE_TYPE_REF}.",
    "preset": f"Deck options preset: {_PRESET_REF}.",
    "cardId": f"Card ID ({_ID}).",
    "cardIds": f"Card IDs ({_ID}).",
    "noteId": f"Note ID ({_ID}).",
    "noteIds": f"Note IDs ({_ID}).",
    "rating": "Answer button: again, hard, good or easy.",
    "includeChildren": "Include subdecks of `deck`.",
    "membership": (
        "How `deck` is matched for cards in filtered decks: `current` = the deck the card is in now, "
        "`home` = its original (home) deck. Default `current`."
    ),
    "filename": "Media file basename (no directories), as stored in the collection media folder.",
    "operationId": "`operationId` from the operation handle returned by a long-running tool (or by `operations_get`).",
    "rescheduleFsrs": "With FSRS enabled, reschedule affected cards after the change. Default false.",
}

# Arguments whose meaning depends on the method; these take precedence over COMMON.
BY_METHOD: dict[str, dict[str, str]] = {
    "profiles.switch": {"name": "Name of the profile to open (see `profiles_list`)."},
    "collection.sync": {
        "includeMedia": "Also sync media (further limited by the profile's media-sync setting). Default true.",
    },
    "collection.refresh": {
        "target": "`windows` refreshes open windows; `cachesAndWindows` also invalidates supported collection caches first.",
    },
    "notes.get": {"id": f"Note ID ({_ID})."},
    "notes.getMany": {"ids": f"Note IDs ({_ID}); results keep input order, including repeats."},
    "notes.search": {"query": "Anki search query for notes, e.g. `deck:Japanese tag:verb`. An empty string matches all notes."},
    "notes.validate": {
        "note": "Note to check, shaped like the `notes_create` arguments: {noteType, deck, fields, tags?, duplicates?}.",
    },
    "notes.validateMany": {"notes": "Notes to check, each shaped like the `notes_create` arguments."},
    "notes.create": {
        "fields": (
            "Field values keyed by exact field name of the note type; values are HTML. "
            'Example: {"Front": "猫", "Back": "cat"}. For media, first call `media_store` and use the returned filename.'
        ),
        "tags": "Tags for the new note (no spaces inside a tag).",
        "duplicates": (
            "Duplicate policy {allow, scope: collection|deck, deck?}. "
            "Default: duplicates of the first field are rejected collection-wide."
        ),
        "rejectEmptyQuestions": "Fail if no card of the note would have a non-empty question. Default true.",
    },
    "notes.createMany": {
        "notes": "Notes to create, each shaped like the `notes_create` arguments.",
        "atomic": (
            "true: preflight the whole batch and add it in one transaction with one undo entry (all or nothing). "
            "false (default): each item is committed independently and reports its own result or error."
        ),
    },
    "notes.update": {
        "id": f"Note ID ({_ID}).",
        "patch": (
            "Changes to apply: {fields?, tags?}. `fields` merges by field name (other fields are kept); "
            "`tags` replaces the whole tag set. Must not be empty."
        ),
    },
    "notes.delete": {"ids": f"Note IDs to delete together with their cards ({_ID})."},
    "notes.planConversion": {
        "source": f"Current note type of the notes: {_NOTE_TYPE_REF}.",
        "target": f"Note type to convert to: {_NOTE_TYPE_REF}.",
    },
    "notes.convert": {
        "ids": f"Notes to convert ({_ID}); all must have the same note type.",
        "target": f"Note type to convert to: {_NOTE_TYPE_REF}.",
        "fields": "Field mapping [{target, source}] (source = old field name or null), usually taken from `notes_planConversion`.",
        "templates": "Template mapping [{target, source}] (source = old template name or null), usually taken from `notes_planConversion`.",
        "planToken": "Token from `notes_planConversion`; it becomes invalid if either note type changes.",
    },
    "notes.findEmpty": {
        "criterion": "What counts as empty: `allFieldsEmpty`, `noCards` or `allQuestionsEmpty`.",
        "query": "Optional Anki search query restricting the candidates. Default: whole collection.",
    },
    "tags.add": {"tags": "Tags to add."},
    "tags.remove": {"tags": "Tags to remove."},
    "tags.replace": {
        "from": "Tag to replace.",
        "to": "Replacement tag.",
        "noteIds": f"Notes to change ({_ID}). Give either this or `allNotes: true`.",
        "allNotes": "Set true (instead of `noteIds`) to replace the tag on all notes.",
    },
    "cards.get": {"id": f"Card ID ({_ID})."},
    "cards.getMany": {"ids": f"Card IDs ({_ID}); results keep input order."},
    "cards.search": {"query": "Anki search query for cards, e.g. `deck:Japanese is:due`. An empty string matches all cards."},
    "cards.render": {"id": f"Card ID ({_ID})."},
    "cards.move": {
        "ids": f"Card IDs ({_ID}).",
        "deck": f"Destination deck: {_DECK_REF}.",
    },
    "cards.setSuspended": {
        "ids": f"Card IDs ({_ID}).",
        "suspended": "true to suspend, false to unsuspend.",
    },
    "cards.setFlags": {
        "ids": f"Card IDs ({_ID}).",
        "flag": "Flag: 0 none, 1 red, 2 orange, 3 green, 4 blue, 5 pink, 6 turquoise, 7 purple.",
    },
    "scheduling.getQueue": {"fetchLimit": "How many queued cards to return, 1–1000 (default 1)."},
    "scheduling.getDue": {"includeLearnAhead": "Treat learning cards within the learn-ahead limit as due. Default false."},
    "scheduling.answer": {
        "stateToken": "`stateToken` from `scheduling_predict` for this card, obtained immediately before answering.",
        "elapsedMs": "Time spent on the card in milliseconds, recorded in review history. Default 0.",
    },
    "scheduling.answerMany": {
        "answers": "Answers [{cardId, rating, stateToken, elapsedMs?}], each like the `scheduling_answer` arguments.",
    },
    "scheduling.reset": {
        "cardIds": f"Cards to reset to new ({_ID}).",
        "restorePosition": "Restore the original new-card position where known. Default true.",
        "resetCounts": "Also reset repetition and lapse counts. Default false.",
        "log": "Add a manual entry to review history. Default true.",
    },
    "scheduling.setDueDate": {
        "days": (
            "Anki due-date syntax: `0` = today, `1` = tomorrow, `3-7` = random day in the range; "
            "append `!` (e.g. `5!`) to also set the interval."
        ),
    },
    "decks.create": {"name": "Full deck name; `::` separates levels, e.g. `Japanese::Verbs`."},
    "decks.update": {"name": "New full deck name; `::` separates levels."},
    "decks.delete": {"deleteCards": "Must be true: confirms that the decks' cards are deleted as well."},
    "deckPresets.create": {
        "name": "Name of the new preset.",
        "cloneFrom": f"Preset to copy settings from: {_PRESET_REF}. Omit to start from Anki defaults.",
    },
    "deckPresets.update": {
        "name": "New preset name.",
        "settings": "Settings to change; only supplied keys are updated (e.g. newPerDay, reviewsPerDay, learnStepsMinutes, desiredRetention).",
    },
    "deckPresets.assign": {"decks": f"Decks to assign the preset to, each {_DECK_REF}."},
    "deckPresets.delete": {
        "replacement": f"Preset for decks that use the deleted one: {_PRESET_REF}. Required if the preset is in use.",
    },
    "noteTypes.create": {
        "name": "Name of the new note type.",
        "kind": "`normal` or `cloze`. Default normal.",
        "fields": "Ordered field definitions [{name, ...}].",
        "templates": "Card templates [{name, questionHtml, answerHtml}]; field references use {{Field}} syntax.",
        "css": "Card styling shared by all templates.",
        "sortField": "Name of the field shown in the browser's sort column. Default: the first field.",
        "latexHeader": "LaTeX preamble.",
        "latexFooter": "LaTeX postamble.",
        "latexSvg": "Render LaTeX as SVG instead of PNG. Default false.",
    },
    "noteTypes.update": {
        "patch": "Non-structural changes: {name?, css?, sortField?, latexHeader?, latexFooter?, latexSvg?}. Must not be empty.",
    },
    "noteTypes.editStructure": {
        "edits": (
            "Ordered structural edits, each {op, ...} with op one of addField, updateField, moveField, removeField, "
            "addTemplate, updateTemplate, moveTemplate, removeTemplate. Saved once after all edits apply."
        ),
    },
    "noteTypes.replaceText": {
        "find": "Literal text to find (not a regex).",
        "replace": "Replacement text (may be empty).",
        "noteTypes": f"Note types to change, each {_NOTE_TYPE_REF}. Give either this or `allNoteTypes: true`.",
        "allNoteTypes": "Set true (instead of `noteTypes`) to change all note types.",
        "targets": "Where to replace: any of question, answer, css. Default all three.",
    },
    "noteTypes.deleteUnused": {"noteTypes": f"Note types to delete if unused, each {_NOTE_TYPE_REF}."},
    "media.store": {
        "filename": (
            "Requested basename, e.g. `cat.jpg`. Anki may normalize or rename it — put the returned "
            "filename into note fields (`<img src=\"...\">` or `[sound:...]`)."
        ),
        "source": (
            'Bytes to store: {"data": "<base64>"}, {"path": "<file on the machine running Anki>"} '
            'or {"url": "<http(s) URL>"}. Max 64 MiB; prefer path for large files.'
        ),
        "collision": "If the name exists: `rename` (default), `replace` or `error`.",
        "skipIfHash": "Optional {algorithm: md5|sha256, digest}: skip storing if the incoming bytes have this hash.",
    },
    "media.get": {"filename": "Media file basename to read."},
    "media.list": {"pattern": "Basename glob, e.g. `*.mp3`. Default `*`."},
    "media.delete": {"filename": "Media file basename to move to Anki's trash."},
    "reviews.list": {
        "cardIds": f"Only reviews of these cards ({_ID}). Mutually exclusive with `deck`; with neither, all history.",
        "deck": f"Only reviews of cards in this deck: {_DECK_REF}. Mutually exclusive with `cardIds`.",
        "includeChildren": "Include subdecks of `deck`. Default false.",
        "afterId": "Only reviews with an ID greater than this one (exclusive), e.g. the latest ID you already have.",
        "includeManual": "Include manual entries (rescheduling, resets), not only answers. Default true.",
    },
    "reviews.getLatestId": {
        "cardIds": f"Only reviews of these cards ({_ID}). Mutually exclusive with `deck`.",
        "deck": f"Only reviews of cards in this deck: {_DECK_REF}. Mutually exclusive with `cardIds`.",
    },
    "statistics.getSummary": {"deck": f"Deck (with subdecks): {_DECK_REF}. Omit for the whole collection."},
    "statistics.getHtml": {"deck": f"Deck (with subdecks): {_DECK_REF}. Omit for the whole collection."},
    "packages.import": {"path": "Path to an .apkg/.colpkg file on the machine running Anki."},
    "packages.export": {
        "deck": f"Deck to export: {_DECK_REF}.",
        "path": "Output .apkg path on the machine running Anki.",
        "includeScheduling": "Include review history and scheduling. Default false.",
    },
    "browser.open": {"query": "Search to show in the browser; omit to keep the browser's default."},
    "browser.select": {
        "cardIds": f"Cards to select ({_ID}). Give either this or `noteIds`.",
        "noteIds": f"Notes to select ({_ID}). Give either this or `cardIds`.",
    },
    "editors.openNote": {"noteId": f"Note to edit ({_ID})."},
    "editors.openAdd": {"note": "Optional draft to prefill: {noteType?, deck?, fields?, tags?}."},
    "editors.updateDraft": {
        "editorId": "Editor `id` from the completed `editors_openAdd` operation.",
        "patch": "Draft changes: {noteType?, deck?, fields?, tags?}.",
        "mode": "`replace` (default) overwrites supplied fields/tags; `append` appends to fields and unions tags.",
    },
    "reviewer.startTimer": {"stateToken": "Current `stateToken` from `reviewer_get`."},
    "reviewer.showQuestion": {"stateToken": "Current `stateToken` from `reviewer_get`."},
    "reviewer.showAnswer": {"stateToken": "Current `stateToken` from `reviewer_get`."},
    "reviewer.answer": {
        "stateToken": "Current `stateToken` from `reviewer_get`, taken after the answer is shown.",
    },
    "reviewer.playAudio": {"stateToken": "Current `stateToken` from `reviewer_get`."},
    "application.navigate": {
        "view": "`deckBrowser`, `deckOverview` or `review`.",
        "deck": f"Deck for deckOverview/review: {_DECK_REF}.",
    },
    "application.importFile": {"path": "File to import on the machine running Anki; omit to let the user choose."},
    "advanced.cards.update": {
        "patch": (
            "Expert scheduling fields to set: {intervalDays?, sm2EasePermille?, repetitions?, lapses?, "
            "remainingSteps?, fsrsMemory?, customData?}."
        ),
    },
    "advanced.reviews.import": {"reviews": "Historical review-log records to add (they do not reschedule cards)."},
    "api.execute": {
        "commands": (
            'Ordered commands [{"method": "notes.create", "params": {...}}] using API method names '
            "(dot form). Each runs after the previous finishes; results are not substituted into later params."
        ),
    },
}


def describe(method: str, argument: str) -> str | None:
    return BY_METHOD.get(method, {}).get(argument) or COMMON.get(argument)
