package diff

// Verdict summarises how two runs differ.
func Verdict(changed int) string {
	if changed == 0 {
		return "same"
	}
	return "changed"
}
