// Package store persists runs. Every backend must pass RunConformance.
package store

import (
	"errors"
	"time"

	"example.com/trackbook/internal/lineage"
)

var (
	ErrNotFound   = errors.New("run not found")
	ErrExists     = errors.New("run already exists")
	ErrTransition = errors.New("invalid status transition")
)

// Patch is a partial update. Nil fields are left unchanged.
type Patch struct {
	Status  *lineage.Status
	EndedAt *time.Time
}

// Store is the persistence contract shared by the Memory and DuckDB backends.
type Store interface {
	Record(run lineage.Run) error
	Get(id string) (lineage.Run, error)
	Update(id string, p Patch) (lineage.Run, error)
	List() ([]lineage.Run, error)
}

// applyPatch is the one place transition rules live, so both backends agree.
func applyPatch(current lineage.Run, p Patch) (lineage.Run, error) {
	updated := current
	if p.Status != nil && *p.Status != current.Status {
		if lineage.Terminal(current.Status) {
			return current, ErrTransition
		}
		updated.Status = *p.Status
	}
	if p.EndedAt != nil {
		updated.EndedAt = *p.EndedAt
	}
	if err := updated.Validate(); err != nil {
		return current, err
	}
	return updated, nil
}
