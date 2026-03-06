// Package output provides formatted output helpers (table, JSON, CSV).
package output

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/fatih/color"
	"github.com/spf13/viper"
)

// Format identifies an output format.
type Format string

const (
	Table Format = "table"
	JSON  Format = "json"
	CSV   Format = "csv"
)

// Current returns the user-selected output format.
func Current() Format {
	f := strings.ToLower(viper.GetString("output"))
	switch Format(f) {
	case JSON, CSV:
		return Format(f)
	default:
		return Table
	}
}

// PrintJSON marshals v to indented JSON and prints it.
func PrintJSON(v interface{}) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}

// PrintCSV writes header + rows as CSV.
func PrintCSV(header []string, rows [][]string) {
	w := csv.NewWriter(os.Stdout)
	_ = w.Write(header)
	for _, r := range rows {
		_ = w.Write(r)
	}
	w.Flush()
}

// PrintTable renders a simple aligned table to stdout.
func PrintTable(header []string, rows [][]string) {
	if len(rows) == 0 {
		fmt.Println("No results.")
		return
	}

	// Calculate column widths
	widths := make([]int, len(header))
	for i, h := range header {
		widths[i] = len(h)
	}
	for _, row := range rows {
		for i := 0; i < len(row) && i < len(widths); i++ {
			if len(row[i]) > widths[i] {
				widths[i] = len(row[i])
			}
		}
	}

	// Print header
	noColor := viper.GetBool("no_color")
	printRow(os.Stdout, header, widths, !noColor)
	printSep(os.Stdout, widths)
	for _, row := range rows {
		printRow(os.Stdout, row, widths, false)
	}
}

func printRow(w io.Writer, cols []string, widths []int, bold bool) {
	for i, col := range cols {
		width := 12
		if i < len(widths) {
			width = widths[i]
		}
		if bold {
			s := color.New(color.Bold).Sprintf("%-*s", width, col)
			fmt.Fprintf(w, "  %s", s)
		} else {
			fmt.Fprintf(w, "  %-*s", width, col)
		}
	}
	fmt.Fprintln(w)
}

func printSep(w io.Writer, widths []int) {
	for _, width := range widths {
		fmt.Fprintf(w, "  %s", strings.Repeat("─", width))
	}
	fmt.Fprintln(w)
}

// Success prints a green success message.
func Success(msg string, args ...interface{}) {
	if viper.GetBool("no_color") {
		fmt.Printf("✓ "+msg+"\n", args...)
		return
	}
	color.Green("✓ "+msg, args...)
}

// Error prints a red error message.
func Error(msg string, args ...interface{}) {
	if viper.GetBool("no_color") {
		fmt.Fprintf(os.Stderr, "✗ "+msg+"\n", args...)
		return
	}
	color.Red("✗ "+msg, args...)
}

// Warn prints a yellow warning message.
func Warn(msg string, args ...interface{}) {
	if viper.GetBool("no_color") {
		fmt.Printf("⚠ "+msg+"\n", args...)
		return
	}
	color.Yellow("⚠ "+msg, args...)
}
