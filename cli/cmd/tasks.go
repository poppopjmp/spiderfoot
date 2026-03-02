package cmd

import (
	"fmt"
	"net/url"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// tasksCmd uses the real API endpoints at /api/tasks/*.
var tasksCmd = &cobra.Command{
	Use:   "tasks",
	Short: "Manage background tasks",
}

var tasksListCmd = &cobra.Command{
	Use:   "list",
	Short: "List tasks",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		state, _ := cmd.Flags().GetString("state")
		taskType, _ := cmd.Flags().GetString("type")
		limit, _ := cmd.Flags().GetInt("limit")

		params := url.Values{}
		if state != "" {
			params.Set("state", state)
		}
		if taskType != "" {
			params.Set("task_type", taskType)
		}
		if limit > 0 {
			params.Set("limit", fmt.Sprintf("%d", limit))
		}

		path := "/api/tasks"
		if q := params.Encode(); q != "" {
			path += "?" + q
		}

		var resp interface{}
		if err := c.Get(path, &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if items, ok := resp.([]interface{}); ok {
				header := []string{"ID", "Type", "State", "Created"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["task_id"]),
							fmt.Sprintf("%v", m["task_type"]),
							fmt.Sprintf("%v", m["state"]),
							fmt.Sprintf("%v", m["created_at"]),
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

var tasksActiveCmd = &cobra.Command{
	Use:   "active",
	Short: "List active tasks",
	RunE:  simpleGet("/api/tasks/active"),
}

var tasksGetCmd = &cobra.Command{
	Use:   "get [task-id]",
	Short: "Get task details",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "task ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/tasks/%s", args[0]), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var tasksCancelCmd = &cobra.Command{
	Use:   "cancel [task-id]",
	Short: "Cancel a task",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "task ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/tasks/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("Task %s cancelled", args[0])
		return nil
	},
}

var tasksCleanCmd = &cobra.Command{
	Use:   "clean",
	Short: "Remove completed tasks",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		if err := c.Delete("/api/tasks/completed", nil); err != nil {
			return err
		}
		output.Success("Completed tasks removed")
		return nil
	},
}

func init() {
	tasksListCmd.Flags().String("state", "", "Filter by state")
	tasksListCmd.Flags().String("type", "", "Filter by task type")
	tasksListCmd.Flags().Int("limit", 50, "Maximum tasks to return")

	tasksCmd.AddCommand(tasksListCmd)
	tasksCmd.AddCommand(tasksActiveCmd)
	tasksCmd.AddCommand(tasksGetCmd)
	tasksCmd.AddCommand(tasksCancelCmd)
	tasksCmd.AddCommand(tasksCleanCmd)
	rootCmd.AddCommand(tasksCmd)
}
