package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// --- Scan types ---

var safeIDRe = regexp.MustCompile(`^[a-zA-Z0-9_\-]{1,64}$`)

func validateSafeID(id, label string) error {
	if !safeIDRe.MatchString(id) {
		return fmt.Errorf("invalid %s: must be 1-64 alphanumeric/dash/underscore characters", label)
	}
	return nil
}

type scanSummary struct {
	ScanID    string  `json:"scan_id"`
	Name      string  `json:"name"`
	Target    string  `json:"target"`
	Status    string  `json:"status"`
	StartedAt float64 `json:"started"`
	EndedAt   float64 `json:"ended"`
}

type scansResp struct {
	Scans []scanSummary `json:"scans"`
}

type scanDetail struct {
	ScanID       string  `json:"scan_id"`
	Name         string  `json:"name"`
	Target       string  `json:"target"`
	Status       string  `json:"status"`
	Progress     int     `json:"progress"`
	ModulesTotal int     `json:"modules_total"`
	ModulesDone  int     `json:"modules_done"`
	EventCount   int     `json:"event_count"`
	StartedAt    float64 `json:"started"`
	EndedAt      float64 `json:"ended"`
}

type scanStartReq struct {
	Target   string   `json:"target"`
	ScanName string   `json:"scan_name"`
	ScanType string   `json:"scan_type"`
	Modules  []string `json:"modules,omitempty"`
}

// --- Commands ---

var scanCmd = &cobra.Command{
	Use:   "scan",
	Short: "Manage scans",
}

var scanListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all scans",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp scansResp
		if err := c.Get("/api/scans", &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp.Scans)
		case output.CSV:
			header := []string{"ID", "Name", "Target", "Status", "Started"}
			rows := make([][]string, 0, len(resp.Scans))
			for _, s := range resp.Scans {
				rows = append(rows, []string{s.ScanID, s.Name, s.Target, s.Status, formatEpoch(s.StartedAt)})
			}
			output.PrintCSV(header, rows)
		default:
			header := []string{"ID", "Name", "Target", "Status", "Started"}
			rows := make([][]string, 0, len(resp.Scans))
			for _, s := range resp.Scans {
				rows = append(rows, []string{truncID(s.ScanID), s.Name, s.Target, colorStatus(s.Status), formatEpoch(s.StartedAt)})
			}
			output.PrintTable(header, rows)
		}
		return nil
	},
}

var scanGetCmd = &cobra.Command{
	Use:   "get [scan-id]",
	Short: "Get scan details",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "scan ID"); err != nil {
			return err
		}
		c := client.New()
		var s scanDetail
		if err := c.Get(fmt.Sprintf("/api/scans/%s", args[0]), &s); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(s)
		default:
			fmt.Printf("Scan ID:       %s\n", s.ScanID)
			fmt.Printf("Name:          %s\n", s.Name)
			fmt.Printf("Target:        %s\n", s.Target)
			fmt.Printf("Status:        %s\n", colorStatus(s.Status))
			fmt.Printf("Progress:      %d%%\n", s.Progress)
			fmt.Printf("Modules:       %d / %d\n", s.ModulesDone, s.ModulesTotal)
			fmt.Printf("Events:        %d\n", s.EventCount)
			fmt.Printf("Started:       %s\n", formatEpoch(s.StartedAt))
			if s.EndedAt > 0 {
				fmt.Printf("Ended:         %s\n", formatEpoch(s.EndedAt))
			}
		}
		return nil
	},
}

var scanStartCmd = &cobra.Command{
	Use:   "start",
	Short: "Start a new scan",
	RunE: func(cmd *cobra.Command, args []string) error {
		target, _ := cmd.Flags().GetString("target")
		name, _ := cmd.Flags().GetString("name")
		scanType, _ := cmd.Flags().GetString("type")
		modules, _ := cmd.Flags().GetString("modules")

		if target == "" {
			return fmt.Errorf("--target is required")
		}
		if name == "" {
			name = "CLI scan: " + target
		}

		body := scanStartReq{
			Target:   target,
			ScanName: name,
			ScanType: scanType,
		}
		if modules != "" {
			body.Modules = strings.Split(modules, ",")
		}

		payload, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("marshaling request: %w", err)
		}
		c := client.New()
		var resp map[string]interface{}
		if err := c.Post("/api/scans", bytes.NewReader(payload), &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if id, ok := resp["scan_id"]; ok {
				output.Success("Scan started: %v", id)
			} else {
				output.Success("Scan started")
				output.PrintJSON(resp)
			}
		}
		return nil
	},
}

var scanStopCmd = &cobra.Command{
	Use:   "stop [scan-id]",
	Short: "Stop a running scan",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "scan ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Post(fmt.Sprintf("/api/scans/%s/stop", args[0]), nil, nil); err != nil {
			return err
		}
		output.Success("Scan %s stopped", args[0])
		return nil
	},
}

var scanDeleteCmd = &cobra.Command{
	Use:   "delete [scan-id]",
	Short: "Delete a scan and its results",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "scan ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/scans/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("Scan %s deleted", args[0])
		return nil
	},
}

// --- Helpers ---

func colorStatus(s string) string {
	switch strings.ToUpper(s) {
	case "RUNNING", "STARTED":
		return color.YellowString(s)
	case "FINISHED", "COMPLETED":
		return color.GreenString(s)
	case "FAILED", "ERROR", "ABORTED":
		return color.RedString(s)
	default:
		return s
	}
}

func truncID(id string) string {
	if len(id) > 12 {
		return id[:12]
	}
	return id
}

func formatEpoch(epoch float64) string {
	if epoch <= 0 {
		return "—"
	}
	t := time.Unix(int64(epoch), 0)
	return t.Local().Format("2006-01-02 15:04")
}

func init() {
	scanStartCmd.Flags().StringP("target", "t", "", "Scan target (required)")
	scanStartCmd.Flags().StringP("name", "n", "", "Scan name")
	scanStartCmd.Flags().String("type", "all", "Scan type: all, passive, investigate, footprint")
	scanStartCmd.Flags().String("modules", "", "Comma-separated list of modules to use")

	scanCmd.AddCommand(scanListCmd)
	scanCmd.AddCommand(scanGetCmd)
	scanCmd.AddCommand(scanStartCmd)
	scanCmd.AddCommand(scanStopCmd)
	scanCmd.AddCommand(scanDeleteCmd)
	rootCmd.AddCommand(scanCmd)
}
