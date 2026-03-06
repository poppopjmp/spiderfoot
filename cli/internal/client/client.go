// Package client provides a typed HTTP client for the SpiderFoot REST API.
package client

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Version is set at build time via -ldflags and used in User-Agent headers.
var Version = "dev"

// Client talks to the SpiderFoot API.
type Client struct {
	BaseURL    string
	APIKey     string
	Token      string
	HTTPClient *http.Client
}

// New creates a Client from the current viper config.
func New() *Client {
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: viper.GetBool("insecure"),
		},
	}
	return &Client{
		BaseURL: strings.TrimRight(viper.GetString("server"), "/"),
		APIKey:  viper.GetString("api_key"),
		Token:   viper.GetString("token"),
		HTTPClient: &http.Client{
			Timeout:   30 * time.Second,
			Transport: transport,
		},
	}
}

// request builds and executes an HTTP request, returning the decoded JSON body.
func (c *Client) request(method, path string, body io.Reader, result interface{}) error {
	u, err := url.JoinPath(c.BaseURL, path)
	if err != nil {
		return fmt.Errorf("invalid URL: %w", err)
	}

	req, err := http.NewRequest(method, u, body)
	if err != nil {
		return fmt.Errorf("creating request: %w", err)
	}

	// Auth
	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	} else if c.APIKey != "" {
		req.Header.Set("X-API-Key", c.APIKey)
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "SpiderFoot-CLI/"+Version)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("reading response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(data), 200))
	}

	if result != nil {
		if err := json.Unmarshal(data, result); err != nil {
			return fmt.Errorf("decoding response: %w", err)
		}
	}
	return nil
}

// Get performs a GET request.
func (c *Client) Get(path string, result interface{}) error {
	return c.request(http.MethodGet, path, nil, result)
}

// Post performs a POST request with a JSON body.
func (c *Client) Post(path string, body io.Reader, result interface{}) error {
	return c.request(http.MethodPost, path, body, result)
}

// Put performs a PUT request with a JSON body.
func (c *Client) Put(path string, body io.Reader, result interface{}) error {
	return c.request(http.MethodPut, path, body, result)
}

// Patch performs a PATCH request with a JSON body.
func (c *Client) Patch(path string, body io.Reader, result interface{}) error {
	return c.request(http.MethodPatch, path, body, result)
}

// Delete performs a DELETE request.
func (c *Client) Delete(path string, result interface{}) error {
	return c.request(http.MethodDelete, path, nil, result)
}

// GetRaw performs a GET request returning raw bytes (for exports).
func (c *Client) GetRaw(path string) ([]byte, string, error) {
	u, err := url.JoinPath(c.BaseURL, path)
	if err != nil {
		return nil, "", fmt.Errorf("invalid URL: %w", err)
	}

	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return nil, "", fmt.Errorf("creating request: %w", err)
	}
	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	} else if c.APIKey != "" {
		req.Header.Set("X-API-Key", c.APIKey)
	}
	req.Header.Set("User-Agent", "SpiderFoot-CLI/"+Version)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, "", fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, "", err
	}

	if resp.StatusCode >= 400 {
		return nil, "", fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(data), 200))
	}

	ct := resp.Header.Get("Content-Type")
	return data, ct, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
