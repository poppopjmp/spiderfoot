package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// webhooksCmd uses the real API endpoints at /api/webhooks/*.
var webhooksCmd = &cobra.Command{
	Use:   "webhooks",
	Short: "Manage webhook subscriptions",
}

var webhooksListCmd = &cobra.Command{
	Use:   "list",
	Short: "List webhooks",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp interface{}
		if err := c.Get("/api/webhooks", &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if items, ok := resp.([]interface{}); ok {
				header := []string{"ID", "URL", "Events", "Status"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["webhook_id"]),
							fmt.Sprintf("%v", m["url"]),
							fmt.Sprintf("%v", m["event_types"]),
							fmt.Sprintf("%v", m["enabled"]),
						})
					}
				}
				output.PrintTable(header, rows)
			} else {
				printGenericResponse(resp)
			}
		}
		return nil
	},
}

var webhooksCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a webhook subscription",
	RunE: func(cmd *cobra.Command, args []string) error {
		urlFlag, _ := cmd.Flags().GetString("url")
		if urlFlag == "" {
			return fmt.Errorf("--url is required")
		}
		body := map[string]string{"url": urlFlag}
		payload, _ := json.Marshal(body)

		c := client.New()
		var resp map[string]interface{}
		if err := c.Post("/api/webhooks", bytes.NewReader(payload), &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			output.Success("Webhook created: %v", resp["webhook_id"])
		}
		return nil
	},
}

var webhooksGetCmd = &cobra.Command{
	Use:   "get [webhook-id]",
	Short: "Get webhook details",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "webhook ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/webhooks/%s", args[0]), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var webhooksDeleteCmd = &cobra.Command{
	Use:   "delete [webhook-id]",
	Short: "Delete a webhook",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "webhook ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/webhooks/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("Webhook %s deleted", args[0])
		return nil
	},
}

var webhooksTestCmd = &cobra.Command{
	Use:   "test [webhook-id]",
	Short: "Send a test event to a webhook",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "webhook ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Post(fmt.Sprintf("/api/webhooks/%s/test", args[0]), nil, &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			output.Success("Test event sent")
		}
		return nil
	},
}

var webhooksStatsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Show webhook delivery statistics",
	RunE:  simpleGet("/api/webhooks/stats"),
}

var webhooksEventTypesCmd = &cobra.Command{
	Use:   "event-types",
	Short: "List available webhook event types",
	RunE:  simpleGet("/api/webhooks/event-types"),
}

func init() {
	webhooksCreateCmd.Flags().String("url", "", "Webhook URL (required)")

	webhooksCmd.AddCommand(webhooksListCmd)
	webhooksCmd.AddCommand(webhooksCreateCmd)
	webhooksCmd.AddCommand(webhooksGetCmd)
	webhooksCmd.AddCommand(webhooksDeleteCmd)
	webhooksCmd.AddCommand(webhooksTestCmd)
	webhooksCmd.AddCommand(webhooksStatsCmd)
	webhooksCmd.AddCommand(webhooksEventTypesCmd)
	rootCmd.AddCommand(webhooksCmd)
}
