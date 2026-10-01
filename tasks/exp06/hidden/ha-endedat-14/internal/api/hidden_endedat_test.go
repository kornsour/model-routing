package api

// Hidden grader (exp06 stratum A): the wire format of ended_at.

import (
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"example.com/trackbook/internal/store"
)

func decode(t *testing.T, body []byte) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(body, &m); err != nil {
		t.Fatalf("bad json %s: %v", body, err)
	}
	return m
}

func TestHiddenUnendedRunHasNoEndedAt(t *testing.T) {
	for _, s := range []store.Store{store.NewMemory(), store.NewDuckDB()} {
		h := NewServer(s)
		created := do(t, h, http.MethodPost, "/runs", map[string]any{"id": "w1", "name": "train"})
		got := do(t, h, http.MethodGet, "/runs/w1", nil)
		for label, body := range map[string][]byte{"POST": created.Body.Bytes(), "GET": got.Body.Bytes()} {
			if v, ok := decode(t, body)["ended_at"]; ok && v != nil {
				t.Fatalf("%s response carries ended_at %v for a run that has not ended", label, v)
			}
		}
	}
}

func TestHiddenTerminalPatchDefaultsEndedAt(t *testing.T) {
	h := NewServer(store.NewMemory())
	do(t, h, http.MethodPost, "/runs", map[string]any{"id": "w2"})
	before := time.Now().UTC().Add(-2 * time.Second)
	rec := do(t, h, http.MethodPatch, "/runs/w2", map[string]any{"status": "succeeded"})
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
	raw, _ := decode(t, rec.Body.Bytes())["ended_at"].(string)
	ended, err := time.Parse(time.RFC3339Nano, raw)
	if err != nil || ended.Before(before) || ended.After(time.Now().UTC().Add(2*time.Second)) {
		t.Fatalf("ended_at = %q, want about now", raw)
	}
}

func TestHiddenNonTerminalPatchLeavesEndedAtUnset(t *testing.T) {
	h := NewServer(store.NewMemory())
	do(t, h, http.MethodPost, "/runs", map[string]any{"id": "w3"})
	rec := do(t, h, http.MethodPatch, "/runs/w3", map[string]any{"status": "running"})
	if v, ok := decode(t, rec.Body.Bytes())["ended_at"]; ok && v != nil {
		t.Fatalf("ended_at = %v after a non-terminal patch", v)
	}
}
