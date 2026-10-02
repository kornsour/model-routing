// Package api is the HTTP surface of the ledger.
package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"

	"example.com/trackbook/internal/lineage"
	"example.com/trackbook/internal/store"
)

// Server routes /runs requests to a Store.
type Server struct {
	store store.Store
}

func NewServer(s store.Store) *Server {
	return &Server{store: s}
}

type patchRequest struct {
	Status  *lineage.Status `json:"status"`
	EndedAt *time.Time      `json:"ended_at"`
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/runs/")
	switch {
	case r.URL.Path == "/runs" && r.Method == http.MethodPost:
		s.record(w, r)
	case strings.HasPrefix(r.URL.Path, "/runs/") && r.Method == http.MethodGet:
		s.get(w, id)
	case strings.HasPrefix(r.URL.Path, "/runs/") && r.Method == http.MethodPatch:
		s.update(w, r, id)
	default:
		http.NotFound(w, r)
	}
}

func (s *Server) record(w http.ResponseWriter, r *http.Request) {
	var run lineage.Run
	if err := json.NewDecoder(r.Body).Decode(&run); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if run.Status == "" {
		run.Status = lineage.StatusRunning
	}
	if run.StartedAt.IsZero() {
		run.StartedAt = time.Now().UTC()
	}
	if err := s.store.Record(run); err != nil {
		status := http.StatusBadRequest
		if errors.Is(err, store.ErrExists) {
			status = http.StatusConflict
		}
		http.Error(w, err.Error(), status)
		return
	}
	writeJSON(w, http.StatusCreated, run)
}

func (s *Server) get(w http.ResponseWriter, id string) {
	run, err := s.store.Get(id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (s *Server) update(w http.ResponseWriter, r *http.Request, id string) {
	var req patchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	run, err := s.store.Update(id, store.Patch{Status: req.Status, EndedAt: req.EndedAt})
	switch {
	case errors.Is(err, store.ErrNotFound):
		http.Error(w, err.Error(), http.StatusNotFound)
	case err != nil:
		http.Error(w, err.Error(), http.StatusConflict)
	default:
		writeJSON(w, http.StatusOK, run)
	}
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
