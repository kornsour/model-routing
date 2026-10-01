// Package lineage defines a run and the provenance that identifies it.
package lineage

import (
	"errors"
	"time"
)

// Status is where a run is in its life.
type Status string

const (
	StatusRunning   Status = "running"
	StatusSucceeded Status = "succeeded"
	StatusFailed    Status = "failed"
	StatusCancelled Status = "cancelled"
)

// Terminal reports whether no further transition is allowed from s.
func Terminal(s Status) bool {
	return s == StatusSucceeded || s == StatusFailed || s == StatusCancelled
}

// Run is one execution of a training or evaluation job.
type Run struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Status    Status    `json:"status"`
	StartedAt time.Time `json:"started_at"`
	EndedAt   time.Time `json:"ended_at,omitempty"`

	// Provenance. These feed the identity hash, so their encoding is part of
	// the ledger's compatibility contract.
	ConfigHash       string `json:"config_hash"`
	DatasetVersion   string `json:"dataset_version"`
	ModelVersion     string `json:"model_version"`
	Host             string `json:"host"`
	Device           string `json:"device"`
	FrameworkVersion string `json:"framework_version"`
}

// Validate checks the invariants a stored run must hold.
func (r Run) Validate() error {
	if r.ID == "" {
		return errors.New("run id is required")
	}
	switch r.Status {
	case StatusRunning, StatusSucceeded, StatusFailed, StatusCancelled:
	default:
		return errors.New("unknown status")
	}
	if !r.EndedAt.IsZero() && r.EndedAt.Before(r.StartedAt) {
		return errors.New("ended_at is before started_at")
	}
	return nil
}
