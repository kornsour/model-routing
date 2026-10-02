package store

import (
	"errors"
	"testing"
	"time"

	"example.com/trackbook/internal/lineage"
)

// RunConformance is the contract every backend must satisfy.
func RunConformance(t *testing.T, newStore func() Store) {
	t.Helper()
	start := time.Date(2026, 9, 1, 10, 0, 0, 0, time.UTC)
	run := func(id string) lineage.Run {
		return lineage.Run{ID: id, Name: "train", Status: lineage.StatusRunning, StartedAt: start, ConfigHash: "abc"}
	}

	t.Run("record and get round-trip", func(t *testing.T) {
		s := newStore()
		want := run("r1")
		if err := s.Record(want); err != nil {
			t.Fatal(err)
		}
		got, err := s.Get("r1")
		if err != nil {
			t.Fatal(err)
		}
		g, w := normalizeForCompare(got, want)
		if g != w {
			t.Fatalf("round trip: got %+v want %+v", g, w)
		}
	})

	t.Run("duplicate id", func(t *testing.T) {
		s := newStore()
		_ = s.Record(run("r1"))
		if err := s.Record(run("r1")); !errors.Is(err, ErrExists) {
			t.Fatalf("got %v, want ErrExists", err)
		}
	})

	t.Run("missing run", func(t *testing.T) {
		if _, err := newStore().Get("nope"); !errors.Is(err, ErrNotFound) {
			t.Fatalf("got %v, want ErrNotFound", err)
		}
	})

	t.Run("terminal is final", func(t *testing.T) {
		s := newStore()
		_ = s.Record(run("r1"))
		done := lineage.StatusSucceeded
		if _, err := s.Update("r1", Patch{Status: &done}); err != nil {
			t.Fatal(err)
		}
		again := lineage.StatusRunning
		if _, err := s.Update("r1", Patch{Status: &again}); !errors.Is(err, ErrTransition) {
			t.Fatalf("got %v, want ErrTransition", err)
		}
	})

	t.Run("update sets ended_at", func(t *testing.T) {
		s := newStore()
		_ = s.Record(run("r1"))
		done := lineage.StatusSucceeded
		endedAt := start.Add(90 * time.Minute)
		if _, err := s.Update("r1", Patch{Status: &done, EndedAt: &endedAt}); err != nil {
			t.Fatal(err)
		}
		got, err := s.Get("r1")
		if err != nil {
			t.Fatal(err)
		}
		if !got.EndedAt.Equal(endedAt) {
			t.Fatalf("ended_at = %v, want %v", got.EndedAt, endedAt)
		}
	})

	t.Run("list is ordered", func(t *testing.T) {
		s := newStore()
		_ = s.Record(run("b"))
		_ = s.Record(run("a"))
		runs, err := s.List()
		if err != nil {
			t.Fatal(err)
		}
		if len(runs) != 2 || runs[0].ID != "a" {
			t.Fatalf("list = %+v", runs)
		}
	})
}
