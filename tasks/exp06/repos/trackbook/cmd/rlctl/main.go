// Command rlctl records and finishes runs against a trackbook server.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"
)

func finishRun(base, id, status string) error {
	body, err := json.Marshal(map[string]any{"status": status, "ended_at": time.Now().UTC()})
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPatch, base+"/runs/"+id, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("finish %s: %s", id, resp.Status)
	}
	return nil
}

func main() {
	base := flag.String("server", "http://127.0.0.1:8787", "trackbook server")
	flag.Parse()
	if flag.NArg() != 3 || flag.Arg(0) != "finish" {
		fmt.Fprintln(os.Stderr, "usage: rlctl finish <id> <status>")
		os.Exit(2)
	}
	if err := finishRun(*base, flag.Arg(1), flag.Arg(2)); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
