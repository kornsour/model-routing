package store

import (
	"sort"
	"sync"

	"example.com/trackbook/internal/lineage"
)

// Memory is an in-process Store for tests and the CLI's dry-run mode.
type Memory struct {
	mu   sync.Mutex
	runs map[string]lineage.Run
}

func NewMemory() *Memory {
	return &Memory{runs: map[string]lineage.Run{}}
}

func (m *Memory) Record(run lineage.Run) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if err := run.Validate(); err != nil {
		return err
	}
	if _, ok := m.runs[run.ID]; ok {
		return ErrExists
	}
	m.runs[run.ID] = run
	return nil
}

func (m *Memory) Get(id string) (lineage.Run, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	run, ok := m.runs[id]
	if !ok {
		return lineage.Run{}, ErrNotFound
	}
	return run, nil
}

func (m *Memory) Update(id string, p Patch) (lineage.Run, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	run, ok := m.runs[id]
	if !ok {
		return lineage.Run{}, ErrNotFound
	}
	updated, err := applyPatch(run, p)
	if err != nil {
		return run, err
	}
	m.runs[id] = updated
	return updated, nil
}

func (m *Memory) List() ([]lineage.Run, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]lineage.Run, 0, len(m.runs))
	for _, r := range m.runs {
		out = append(out, r)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out, nil
}
