package tools

import "testing"

func TestChunkShortTextIsOnePiece(t *testing.T) {
	got := chunk("short", maxInputChars())
	if len(got) != 1 || got[0] != "short" {
		t.Fatalf("got %v", got)
	}
}

func TestChunkSplitsAndKeepsEverything(t *testing.T) {
	body := ""
	for i := 0; i < 3000; i++ {
		body += "line of prose that is reasonably long\n"
	}

	size := embedBudget(documentPrefix())
	parts := chunk(body, size)
	if len(parts) < 2 {
		t.Fatalf("expected several chunks, got %d", len(parts))
	}
	for i, p := range parts {
		if n := len([]rune(p)); n > size {
			t.Fatalf("chunk %d is %d runes, over the %d limit", i, n, size)
		}
	}

	// Every chunk after the first repeats the tail of the one before, so the
	// pieces cover the input with no gap.
	joined := parts[0]
	for _, p := range parts[1:] {
		joined += p
	}
	if len([]rune(joined)) < len([]rune(body)) {
		t.Fatalf("chunks lost content: %d < %d", len([]rune(joined)), len([]rune(body)))
	}
	t.Logf("%d chars -> %d chunks", len([]rune(body)), len(parts))
}

// The prefix is prepended after chunking, so a chunk sized at the full cap
// would go to the server over it. The budget has to come off the front.
func TestChunkLeavesRoomForThePrefix(t *testing.T) {
	prefix := documentPrefix()
	if prefix == "" {
		t.Skip("no prefix configured")
	}

	body := ""
	for i := 0; i < 3000; i++ {
		body += "line of prose that is reasonably long\n"
	}

	for i, p := range chunk(body, embedBudget(prefix)) {
		if n := len([]rune(prefix + p)); n > maxInputChars() {
			t.Fatalf("chunk %d is %d runes with the prefix, over the %d cap", i, n, maxInputChars())
		}
	}
}

// A prefix longer than the whole cap must not produce a negative budget.
func TestEmbedBudgetNeverGoesBelowOne(t *testing.T) {
	t.Setenv("EMBEDDING_MAX_INPUT_CHARS", "4")
	if got := embedBudget("search_document: "); got != 1 {
		t.Fatalf("got %d, want 1", got)
	}
}
