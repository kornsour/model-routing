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
	if !r.EndedAt.IsZero() {
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
		run.EndedAt = nsToTime(row.EndedAtNS.Int64)
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
// the caller used, and an unset EndedAt must compare equal either way.
func normalizeForCompare(a, b lineage.Run) (lineage.Run, lineage.Run) {
	a.StartedAt, b.StartedAt = a.StartedAt.UTC(), b.StartedAt.UTC()
	if a.EndedAt.IsZero() && b.EndedAt.IsZero() {
		a.EndedAt, b.EndedAt = time.Time{}, time.Time{}
	} else {
		a.EndedAt, b.EndedAt = a.EndedAt.UTC(), b.EndedAt.UTC()
	}
	return a, b
}
