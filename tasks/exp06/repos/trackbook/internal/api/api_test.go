package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"example.com/trackbook/internal/store"
)

func do(t *testing.T, h http.Handler, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	var buf bytes.Buffer
	if body != nil {
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			t.Fatal(err)
		}
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, path, &buf))
	return rec
}

func TestRecordDefaultsStartedAt(t *testing.T) {
	h := NewServer(store.NewMemory())
	rec := do(t, h, http.MethodPost, "/runs", map[string]any{"id": "r1", "name": "train"})
	if rec.Code != http.StatusCreated {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
	var got map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got["started_at"] == "0001-01-01T00:00:00Z" {
		t.Fatal("started_at was not defaulted")
	}
}

func TestDuplicateIsConflict(t *testing.T) {
	h := NewServer(store.NewMemory())
	do(t, h, http.MethodPost, "/runs", map[string]any{"id": "r1"})
	if rec := do(t, h, http.MethodPost, "/runs", map[string]any{"id": "r1"}); rec.Code != http.StatusConflict {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestPatchWithEndedAt(t *testing.T) {
	h := NewServer(store.NewMemory())
	do(t, h, http.MethodPost, "/runs", map[string]any{"id": "r1", "started_at": "2026-09-01T10:00:00Z"})
	rec := do(t, h, http.MethodPatch, "/runs/r1", map[string]any{"status": "succeeded", "ended_at": "2026-09-01T11:30:00Z"})
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
	var got map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got["ended_at"] != "2026-09-01T11:30:00Z" {
		t.Fatalf("ended_at = %v", got["ended_at"])
	}
}

func TestPatchTerminalIsFinal(t *testing.T) {
	h := NewServer(store.NewMemory())
	do(t, h, http.MethodPost, "/runs", map[string]any{"id": "r1"})
	do(t, h, http.MethodPatch, "/runs/r1", map[string]any{"status": "failed"})
	if rec := do(t, h, http.MethodPatch, "/runs/r1", map[string]any{"status": "running"}); rec.Code != http.StatusConflict {
		t.Fatalf("status %d", rec.Code)
	}
}
