package store

import (
	"database/sql"
	"sort"
	"sync"
)

// table stands in for the DuckDB connection in builds without cgo: one row
// type with the same column types the DuckDB schema declares (timestamps as
// BIGINT nanoseconds, nullable where the schema allows NULL), so duckdb.go
// does exactly the conversions it does against the real driver.
type runRow struct {
	ID               string
	Name             string
	Status           string
	StartedAtNS      int64
	EndedAtNS        sql.NullInt64
	ConfigHash       string
	DatasetVersion   string
	ModelVersion     string
	Host             string
	Device           string
	FrameworkVersion string
}

type table struct {
	mu   sync.Mutex
	rows map[string]runRow
}

func newTable() *table { return &table{rows: map[string]runRow{}} }

func (t *table) insert(r runRow) bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	if _, ok := t.rows[r.ID]; ok {
		return false
	}
	t.rows[r.ID] = r
	return true
}

func (t *table) put(r runRow) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.rows[r.ID] = r
}

func (t *table) get(id string) (runRow, bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	r, ok := t.rows[id]
	return r, ok
}

func (t *table) all() []runRow {
	t.mu.Lock()
	defer t.mu.Unlock()
	out := make([]runRow, 0, len(t.rows))
	for _, r := range t.rows {
		out = append(out, r)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}
