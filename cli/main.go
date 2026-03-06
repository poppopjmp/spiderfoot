// SpiderFoot CLI — cross-platform command-line client for the SpiderFoot REST API.
//
// Build: go build -o sf ./
// Usage: sf scan list --server http://localhost:8001
package main

import "github.com/spiderfoot/spiderfoot-cli/cmd"

func main() {
	cmd.Execute()
}
