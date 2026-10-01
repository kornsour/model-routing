package store

import (
	"database/sql"
	"time"

	"example.com/trackbook/internal/lineage"
)

// DuckDB stores runs in a DuckDB file. Timestamps are BIGINT nanoseconds;
// ended_at_ns is nullable because a running run has not ended.
type DuckDB struct {
	t *table
}

func NewDuckDB() *DuckDB {
	return &DuckDB{t: newTable()}
}

func nsToTime(ns int64) time.Time {
	return time.Unix(0, ns).UTC()
}

func toRow(r lineage.Run) runRow {
	var endedAt sql.NullInt64
	if r.EndedAt != nil {
		endedAt = sql.NullInt64{Int64: r.EndedAt.UnixNano(), Valid: true}
	}
	return runRow{
		ID:               r.ID,
		Name:             r.Name,
		Status:           string(r.Status),
		StartedAtNS:      r.StartedAt.UnixNano(),
		EndedAtNS:        endedAt,
		ConfigHash:       r.ConfigHash,
		DatasetVersion:   r.DatasetVersion,
		ModelVersion:     r.ModelVersion,
		Host:             r.Host,
		Device:           r.Device,
		FrameworkVersion: r.FrameworkVersion,
	}
}

func fromRow(row runRow) lineage.Run {
	run := lineage.Run{
		ID:               row.ID,
		Name:             row.Name,
		Status:           lineage.Status(row.Status),
		StartedAt:        nsToTime(row.StartedAtNS),
		ConfigHash:       row.ConfigHash,
		DatasetVersion:   row.DatasetVersion,
		ModelVersion:     row.ModelVersion,
		Host:             row.Host,
		Device:           row.Device,
		FrameworkVersion: row.FrameworkVersion,
	}
	if row.EndedAtNS.Valid {
		t := nsToTime(row.EndedAtNS.Int64)
		run.EndedAt = &t
	}
	return run
}

func (d *DuckDB) Record(run lineage.Run) error {
	if err := run.Validate(); err != nil {
		return err
	}
	if !d.t.insert(toRow(run)) {
		return ErrExists
	}
	return nil
}

func (d *DuckDB) Get(id string) (lineage.Run, error) {
	row, ok := d.t.get(id)
	if !ok {
		return lineage.Run{}, ErrNotFound
	}
	return fromRow(row), nil
}

func (d *DuckDB) Update(id string, p Patch) (lineage.Run, error) {
	row, ok := d.t.get(id)
	if !ok {
		return lineage.Run{}, ErrNotFound
	}
	current := fromRow(row)
	updated, err := applyPatch(current, p)
	if err != nil {
		return current, err
	}
	d.t.put(toRow(updated))
	return updated, nil
}

func (d *DuckDB) List() ([]lineage.Run, error) {
	rows := d.t.all()
	out := make([]lineage.Run, 0, len(rows))
	for _, row := range rows {
		out = append(out, fromRow(row))
	}
	return out, nil
}

// normalizeForCompare makes two runs read back from different backends
// comparable: DuckDB keeps nanoseconds in UTC, Memory keeps whatever location
// the caller used. EndedAt pointers are compared by value: both nil is equal,
// one nil is not, both set compare with Equal.
func normalizeForCompare(a, b lineage.Run) (lineage.Run, lineage.Run) {
	a.StartedAt, b.StartedAt = a.StartedAt.UTC(), b.StartedAt.UTC()
	if a.EndedAt != nil && b.EndedAt != nil && a.EndedAt.Equal(*b.EndedAt) {
		a.EndedAt = b.EndedAt
	}
	return a, b
}
