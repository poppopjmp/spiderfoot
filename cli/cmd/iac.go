package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// --- IaC commands ---

var iacCmd = &cobra.Command{
	Use:   "iac",
	Short: "IaC generation with schema validation",
}

var iacGenerateCmd = &cobra.Command{
	Use:   "generate [scan-id]",
	Short: "Generate validated IaC from scan results",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "scan ID"); err != nil {
			return err
		}
		provider, _ := cmd.Flags().GetString("provider")
		terraform, _ := cmd.Flags().GetBool("terraform")
		ansible, _ := cmd.Flags().GetBool("ansible")
		docker, _ := cmd.Flags().GetBool("docker")
		packer, _ := cmd.Flags().GetBool("packer")
		validate, _ := cmd.Flags().GetBool("validate")

		body := map[string]interface{}{
			"provider":          provider,
			"include_terraform": terraform,
			"include_ansible":   ansible,
			"include_docker":    docker,
			"include_packer":    packer,
			"validate":          validate,
		}
		payload, _ := json.Marshal(body)

		c := client.New()
		var resp map[string]interface{}
		if err := c.Post(fmt.Sprintf("/api/scans/%s/iac", args[0]), bytes.NewReader(payload), &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			fmt.Printf("Provider:  %s\n", provider)
			if summary, ok := resp["profile_summary"].(map[string]interface{}); ok {
				fmt.Printf("IPs:       %.0f\n", summary["ip_count"])
				fmt.Printf("Ports:     %.0f\n", summary["port_count"])
				fmt.Printf("Services:  %.0f\n", summary["service_count"])
			}
			if files, ok := resp["files"].(map[string]interface{}); ok {
				fmt.Println("\nGenerated files:")
				for category, list := range files {
					if items, ok := list.([]interface{}); ok {
						fmt.Printf("  [%s]\n", category)
						for _, f := range items {
							fmt.Printf("    %s\n", f)
						}
					}
				}
			}
			if allValid, ok := resp["all_valid"].(bool); ok {
				if allValid {
					output.Success("All validations passed")
				} else {
					output.Warn("Some validations failed")
				}
			}
		}
		return nil
	},
}

var iacValidateCmd = &cobra.Command{
	Use:   "validate [scan-id]",
	Short: "Validate IaC output for a scan",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "scan ID"); err != nil {
			return err
		}
		body := map[string]interface{}{"validate": true}
		payload, _ := json.Marshal(body)

		c := client.New()
		var resp map[string]interface{}
		if err := c.Post(fmt.Sprintf("/api/scans/%s/iac", args[0]), bytes.NewReader(payload), &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp["validation"])
		default:
			if results, ok := resp["validation"].([]interface{}); ok {
				passed, failed := 0, 0
				for _, r := range results {
					if m, ok := r.(map[string]interface{}); ok {
						if valid, ok := m["valid"].(bool); ok && valid {
							passed++
							fmt.Printf("  [PASS] %s: %s\n", m["artifact_type"], m["file_name"])
						} else {
							failed++
							fmt.Printf("  [FAIL] %s: %s\n", m["artifact_type"], m["file_name"])
							if errors, ok := m["errors"].([]interface{}); ok {
								for _, e := range errors {
									fmt.Printf("         ✗ %s\n", e)
								}
							}
						}
					}
				}
				fmt.Printf("\nValidation: %d passed, %d failed\n", passed, failed)
			}
		}
		return nil
	},
}

var iacProvidersCmd = &cobra.Command{
	Use:   "providers",
	Short: "List supported cloud providers",
	RunE: func(cmd *cobra.Command, args []string) error {
		providers := []map[string]string{
			{"name": "aws", "description": "Amazon Web Services"},
			{"name": "azure", "description": "Microsoft Azure"},
			{"name": "gcp", "description": "Google Cloud Platform"},
			{"name": "digitalocean", "description": "DigitalOcean"},
			{"name": "vmware", "description": "VMware vSphere"},
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(providers)
		default:
			fmt.Println("Supported cloud providers:")
			for _, p := range providers {
				fmt.Printf("  %-15s %s\n", p["name"], p["description"])
			}
		}
		return nil
	},
}

func init() {
	iacGenerateCmd.Flags().String("provider", "aws", "Cloud provider: aws, azure, gcp, digitalocean, vmware")
	iacGenerateCmd.Flags().Bool("terraform", true, "Include Terraform configs")
	iacGenerateCmd.Flags().Bool("ansible", true, "Include Ansible playbook")
	iacGenerateCmd.Flags().Bool("docker", true, "Include Docker Compose")
	iacGenerateCmd.Flags().Bool("packer", false, "Include Packer configs")
	iacGenerateCmd.Flags().Bool("validate", true, "Run schema validation on output")

	iacCmd.AddCommand(iacGenerateCmd)
	iacCmd.AddCommand(iacValidateCmd)
	iacCmd.AddCommand(iacProvidersCmd)
	rootCmd.AddCommand(iacCmd)
}
