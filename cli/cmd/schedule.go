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
	ID             string  `json:"id"`
	Name           string  `json:"name"`
	Target         string  `json:"target"`
	ScanType       string  `json:"scan_type"`
	CronExpression string  `json:"cron_expression"`
	Enabled        bool    `json:"enabled"`
	LastRun        float64 `json:"last_run"`
	NextRun        float64 `json:"next_run"`
	CreatedAt      float64 `json:"created_at"`
}

type schedulesResp struct {
	Schedules []schedule `json:"schedules"`
}

type scheduleCreateReq struct {
	Name           string `json:"name"`
	Target         string `json:"target"`
	ScanType       string `json:"scan_type"`
	CronExpression string `json:"cron_expression"`
	Enabled        bool   `json:"enabled"`
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
			header := []string{"ID", "Name", "Target", "Cron", "Enabled", "Next Run"}
			rows := make([][]string, 0, len(resp.Schedules))
			for _, s := range resp.Schedules {
				rows = append(rows, []string{s.ID, s.Name, s.Target, s.CronExpression, fmt.Sprintf("%v", s.Enabled), formatEpoch(s.NextRun)})
			}
			output.PrintCSV(header, rows)
		default:
			header := []string{"ID", "Name", "Target", "Cron", "Enabled", "Next Run"}
			rows := make([][]string, 0, len(resp.Schedules))
			for _, s := range resp.Schedules {
				enabled := "✓"
				if !s.Enabled {
					enabled = "✗"
				}
				rows = append(rows, []string{truncID(s.ID), s.Name, s.Target, s.CronExpression, enabled, formatEpoch(s.NextRun)})
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
		scanType, _ := cmd.Flags().GetString("type")
		cron, _ := cmd.Flags().GetString("cron")

		if name == "" || target == "" || cron == "" {
			return fmt.Errorf("--name, --target, and --cron are required")
		}

		body := scheduleCreateReq{
			Name:           name,
			Target:         target,
			ScanType:       scanType,
			CronExpression: cron,
			Enabled:        true,
		}
		payload, _ := json.Marshal(body)

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

var scheduleDeleteCmd = &cobra.Command{
	Use:   "delete [schedule-id]",
	Short: "Delete a schedule",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
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
	scheduleCreateCmd.Flags().String("type", "all", "Scan type")
	scheduleCreateCmd.Flags().String("cron", "", "Cron expression (required), e.g. '0 0 * * *'")

	scheduleCmd.AddCommand(scheduleListCmd)
	scheduleCmd.AddCommand(scheduleCreateCmd)
	scheduleCmd.AddCommand(scheduleDeleteCmd)
	scheduleCmd.AddCommand(scheduleTriggerCmd)
	rootCmd.AddCommand(scheduleCmd)
}
