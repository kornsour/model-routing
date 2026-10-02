package store

// Hidden grader (exp06 stratum A): EndedAt is a pointer, nil until a run ends,
// and defaulted to receive time on a terminal transition, on every backend.

import (
	"testing"
	"time"

	"example.com/trackbook/internal/lineage"
)

var (
	_ string = lineage.Run{}.ConfigHash
	_ string = lineage.Run{}.DatasetVersion
	_ string = lineage.Run{}.ModelVersion
	_ string = lineage.Run{}.Host
	_ string = lineage.Run{}.Device
	_ string = lineage.Run{}.FrameworkVersion
)

func TestHiddenEndedAtLifecycle(t *testing.T) {
	backends := map[string]func() Store{
		"memory": func() Store { return NewMemory() },
		"duckdb": func() Store { return NewDuckDB() },
	}
	for name, mk := range backends {
		t.Run(name, func(t *testing.T) {
			s := mk()
			start := time.Now().UTC().Add(-time.Hour).Truncate(time.Second)
			newRun := func(id string) {
				t.Helper()
				if err := s.Record(lineage.Run{ID: id, Name: "x", Status: lineage.StatusRunning, StartedAt: start}); err != nil {
					t.Fatal(err)
				}
			}

			newRun("h1")
			got, err := s.Get("h1")
			if err != nil {
				t.Fatal(err)
			}
			var ended *time.Time = got.EndedAt
			if ended != nil {
				t.Fatalf("a recorded run has EndedAt %v, want nil", *ended)
			}

			done := lineage.StatusSucceeded
			before := time.Now().UTC().Add(-time.Second)
			upd, err := s.Update("h1", Patch{Status: &done})
			if err != nil {
				t.Fatal(err)
			}
			after := time.Now().UTC().Add(time.Second)
			for label, r := range map[string]lineage.Run{"update result": upd, "read back": mustGet(t, s, "h1")} {
				if r.EndedAt == nil || r.EndedAt.Before(before) || r.EndedAt.After(after) {
					t.Fatalf("%s: terminal update without ended_at gave EndedAt %v, want about now", label, r.EndedAt)
				}
			}

			newRun("h2")
			running := lineage.StatusRunning
			u2, err := s.Update("h2", Patch{Status: &running})
			if err != nil {
				t.Fatal(err)
			}
			if u2.EndedAt != nil {
				t.Fatalf("non-terminal update set EndedAt %v", *u2.EndedAt)
			}

			newRun("h3")
			explicit := start.Add(30 * time.Minute)
			failed := lineage.StatusFailed
			u3, err := s.Update("h3", Patch{Status: &failed, EndedAt: &explicit})
			if err != nil {
				t.Fatal(err)
			}
			if u3.EndedAt == nil || !u3.EndedAt.Equal(explicit) {
				t.Fatalf("explicit ended_at not kept: %v", u3.EndedAt)
			}
		})
	}
}

func mustGet(t *testing.T, s Store, id string) lineage.Run {
	t.Helper()
	r, err := s.Get(id)
	if err != nil {
		t.Fatal(err)
	}
	return r
}
