package lineage

import (
	"testing"
	"time"
)

func base() Run {
	return Run{
		ID:        "r1",
		Name:      "train",
		Status:    StatusRunning,
		StartedAt: time.Date(2026, 9, 1, 10, 0, 0, 0, time.UTC),
	}
}

func TestTerminal(t *testing.T) {
	cases := map[Status]bool{
		StatusRunning:   false,
		StatusSucceeded: true,
		StatusFailed:    true,
		StatusCancelled: true,
	}
	for s, want := range cases {
		if got := Terminal(s); got != want {
			t.Errorf("Terminal(%q) = %v, want %v", s, got, want)
		}
	}
}

func TestValidateRequiresID(t *testing.T) {
	r := base()
	r.ID = ""
	if err := r.Validate(); err == nil {
		t.Fatal("expected an error for a missing id")
	}
}

func TestValidateRejectsUnknownStatus(t *testing.T) {
	r := base()
	r.Status = "paused"
	if err := r.Validate(); err == nil {
		t.Fatal("expected an error for an unknown status")
	}
}

func TestValidateAcceptsRunningRun(t *testing.T) {
	if err := base().Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// A run cannot end before it started, but ending at the same instant is fine:
// short evaluation jobs finish inside the clock's resolution.
func TestValidateEndBeforeStart(t *testing.T) {
	r := base()
	r.Status = StatusSucceeded
	r.EndedAt = r.StartedAt.Add(-time.Second)
	if err := r.Validate(); err == nil {
		t.Fatal("expected an error when ended_at precedes started_at")
	}
}

func TestValidateEndAtStart(t *testing.T) {
	r := base()
	r.Status = StatusSucceeded
	r.EndedAt = r.StartedAt
	if err := r.Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
