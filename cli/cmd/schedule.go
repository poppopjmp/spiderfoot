package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

type schedule struct {
	ID            string   `json:"id"`
	Name          string   `json:"name"`
	Target        string   `json:"target"`
	Engine        *string  `json:"engine"`
	Modules       []string `json:"modules"`
	IntervalHours float64  `json:"interval_hours"`
	Enabled       bool     `json:"enabled"`
	Description   string   `json:"description"`
	Tags          []string `json:"tags"`
	RunsCompleted int      `json:"runs_completed"`
	MaxRuns       int      `json:"max_runs"`
	LastRunAt     *float64 `json:"last_run_at"`
	NextRunAt     *float64 `json:"next_run_at"`
	CreatedAt     float64  `json:"created_at"`
}

type schedulesResp struct {
	Schedules []schedule `json:"schedules"`
}

type scheduleCreateReq struct {
	Name          string  `json:"name"`
	Target        string  `json:"target"`
	IntervalHours float64 `json:"interval_hours"`
	Enabled       bool    `json:"enabled"`
	Description   string  `json:"description,omitempty"`
}

var scheduleCmd = &cobra.Command{
	Use:     "schedule",
	Aliases: []string{"schedules"},
	Short:   "Manage recurring scan schedules",
}

var scheduleListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all schedules",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp schedulesResp
		if err := c.Get("/api/schedules", &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp.Schedules)
		case output.CSV:
			header := []string{"ID", "Name", "Target", "Interval", "Enabled", "Runs", "Next Run"}
			rows := make([][]string, 0, len(resp.Schedules))
			for _, s := range resp.Schedules {
				nextRun := float64(0)
				if s.NextRunAt != nil {
					nextRun = *s.NextRunAt
				}
				rows = append(rows, []string{s.ID, s.Name, s.Target, fmt.Sprintf("%.1fh", s.IntervalHours), fmt.Sprintf("%v", s.Enabled), fmt.Sprintf("%d", s.RunsCompleted), formatEpoch(nextRun)})
			}
			output.PrintCSV(header, rows)
		default:
			header := []string{"ID", "Name", "Target", "Interval", "Enabled", "Runs", "Next Run"}
			rows := make([][]string, 0, len(resp.Schedules))
			for _, s := range resp.Schedules {
				enabled := "✓"
				if !s.Enabled {
					enabled = "✗"
				}
				interval := fmt.Sprintf("%.0fh", s.IntervalHours)
				if s.IntervalHours >= 24 {
					interval = fmt.Sprintf("%.0fd", s.IntervalHours/24)
				}
				nextRun := float64(0)
				if s.NextRunAt != nil {
					nextRun = *s.NextRunAt
				}
				runs := fmt.Sprintf("%d", s.RunsCompleted)
				if s.MaxRuns > 0 {
					runs = fmt.Sprintf("%d/%d", s.RunsCompleted, s.MaxRuns)
				}
				rows = append(rows, []string{truncID(s.ID), s.Name, s.Target, interval, enabled, runs, formatEpoch(nextRun)})
			}
			output.PrintTable(header, rows)
		}
		return nil
	},
}

var scheduleCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a new schedule",
	RunE: func(cmd *cobra.Command, args []string) error {
		name, _ := cmd.Flags().GetString("name")
		target, _ := cmd.Flags().GetString("target")
		interval, _ := cmd.Flags().GetFloat64("interval")
		description, _ := cmd.Flags().GetString("description")

		if name == "" || target == "" || interval <= 0 {
			return fmt.Errorf("--name, --target, and --interval (>0) are required")
		}

		body := scheduleCreateReq{
			Name:          name,
			Target:        target,
			IntervalHours: interval,
			Enabled:       true,
			Description:   description,
		}
		payload, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("failed to marshal request: %w", err)
		}

		c := client.New()
		var resp map[string]interface{}
		if err := c.Post("/api/schedules", bytes.NewReader(payload), &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			output.Success("Schedule created: %v", resp["id"])
		}
		return nil
	},
}

var scheduleUpdateCmd = &cobra.Command{
	Use:   "update [schedule-id]",
	Short: "Update a schedule (partial update)",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "schedule ID"); err != nil {
			return err
		}
		updates := make(map[string]interface{})

		if cmd.Flags().Changed("name") {
			v, _ := cmd.Flags().GetString("name")
			updates["name"] = v
		}
		if cmd.Flags().Changed("target") {
			v, _ := cmd.Flags().GetString("target")
			updates["target"] = v
		}
		if cmd.Flags().Changed("interval") {
			v, _ := cmd.Flags().GetFloat64("interval")
			updates["interval_hours"] = v
		}
		if cmd.Flags().Changed("description") {
			v, _ := cmd.Flags().GetString("description")
			updates["description"] = v
		}
		if cmd.Flags().Changed("enabled") {
			v, _ := cmd.Flags().GetBool("enabled")
			updates["enabled"] = v
		}

		if len(updates) == 0 {
			return fmt.Errorf("at least one flag must be specified")
		}

		payload, err := json.Marshal(updates)
		if err != nil {
			return fmt.Errorf("failed to marshal request: %w", err)
		}

		c := client.New()
		var resp map[string]interface{}
		if err := c.Patch(fmt.Sprintf("/api/schedules/%s", args[0]), bytes.NewReader(payload), &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			output.Success("Schedule %s updated", args[0])
		}
		return nil
	},
}

var scheduleDeleteCmd = &cobra.Command{
	Use:   "delete [schedule-id]",
	Short: "Delete a schedule",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "schedule ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/schedules/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("Schedule %s deleted", args[0])
		return nil
	},
}

var scheduleTriggerCmd = &cobra.Command{
	Use:   "trigger [schedule-id]",
	Short: "Manually trigger a scheduled scan",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "schedule ID"); err != nil {
			return err
		}
		c := client.New()
		var resp map[string]interface{}
		if err := c.Post(fmt.Sprintf("/api/schedules/%s/trigger", args[0]), nil, &resp); err != nil {
			return err
		}
		output.Success("Schedule triggered — %v", resp)
		return nil
	},
}

func init() {
	scheduleCreateCmd.Flags().StringP("name", "n", "", "Schedule name (required)")
	scheduleCreateCmd.Flags().StringP("target", "t", "", "Scan target (required)")
	scheduleCreateCmd.Flags().Float64("interval", 24, "Interval in hours between runs (required)")
	scheduleCreateCmd.Flags().StringP("description", "d", "", "Schedule description")

	scheduleUpdateCmd.Flags().StringP("name", "n", "", "New schedule name")
	scheduleUpdateCmd.Flags().StringP("target", "t", "", "New scan target")
	scheduleUpdateCmd.Flags().Float64("interval", 0, "Interval in hours between runs")
	scheduleUpdateCmd.Flags().StringP("description", "d", "", "New description")
	scheduleUpdateCmd.Flags().Bool("enabled", true, "Enable or disable the schedule")

	scheduleCmd.AddCommand(scheduleListCmd)
	scheduleCmd.AddCommand(scheduleCreateCmd)
	scheduleCmd.AddCommand(scheduleUpdateCmd)
	scheduleCmd.AddCommand(scheduleDeleteCmd)
	scheduleCmd.AddCommand(scheduleTriggerCmd)
	rootCmd.AddCommand(scheduleCmd)
}
