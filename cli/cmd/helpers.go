package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// simpleGet returns a cobra.RunE function that GETs the given path and prints the result.
func simpleGet(path string) func(cmd *cobra.Command, args []string) error {
	return func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp interface{}
		if err := c.Get(path, &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			printGenericResponse(resp)
		}
		return nil
	}
}

// printGenericResponse prints an arbitrary response value in a human-readable form.
func printGenericResponse(resp interface{}) {
	switch v := resp.(type) {
	case map[string]interface{}:
		for key, val := range v {
			fmt.Printf("%-24s %v\n", key+":", val)
		}
	case []interface{}:
		for i, item := range v {
			fmt.Printf("[%d] %v\n", i, item)
		}
	default:
		fmt.Println(resp)
	}
}
