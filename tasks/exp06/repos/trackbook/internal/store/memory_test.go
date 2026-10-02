package store

import "testing"

func TestMemoryConformance(t *testing.T) {
	RunConformance(t, func() Store { return NewMemory() })
}
