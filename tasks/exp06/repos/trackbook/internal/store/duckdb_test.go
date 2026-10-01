package store

import "testing"

func TestDuckDBConformance(t *testing.T) {
	RunConformance(t, func() Store { return NewDuckDB() })
}
