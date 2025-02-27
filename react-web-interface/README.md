# SpiderFoot React Web Interface

This is an alternative web interface for SpiderFoot using React. It provides a completely new design and does not reuse any files from the current web interface.

## Prerequisites

- Node.js (v14 or higher)
- npm (v6 or higher)
- alertifyjs
- bootstrap
- d3
- jquery
- sigma
- tablesorter

## Installation

1. Clone the repository:

```bash
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot/react-web-interface
```

2. Install the dependencies:

```bash
npm install
```

3. Build the React app:

```bash
npm run build
```

4. Start the production server:

```bash
npm start
```

This will build the React app and start the Express.js server to serve the production version of the app.

## Available Scripts

In the project directory, you can run the following scripts:

### `npm start`

Runs the Express.js server.

### `npm run client`

Runs the React development server.

### `npm run server`

Runs the Express.js server with nodemon for automatic restarts.

### `npm run dev`

Runs both the Express.js server and the React development server concurrently.

### `npm run build`

Builds the React app for production.

## Project Structure

The project structure is as follows:

```
react-web-interface/
├── client/
│   ├── public/
│   ├── src/
│   │   ├── App.js
│   │   ├── index.js
│   │   └── ...
│   └── package.json
├── server.js
├── package.json
└── README.md
```

- `client/`: Contains the React front-end code.
- `server.js`: Contains the Express.js server code.
- `package.json`: Contains the project dependencies and scripts.
- `README.md`: This file.

## Usage

The React web interface provides the following functionalities:

- Start a scan
- Stop a scan
- Retrieve scan results
- List available modules
- List active scans
- Get scan status
- List scan history
- Export scan results
- Import API keys
- Export API keys

### Start a Scan

To start a new scan, enter the target and select the modules you want to use, then click the "Start Scan" button.

### Stop a Scan

To stop an ongoing scan, enter the scan ID and click the "Stop Scan" button.

### Retrieve Scan Results

To retrieve the results of a completed scan, enter the scan ID and click the "Get Scan Results" button.

### List Available Modules

The available modules are listed in the "Start Scan" section. You can select multiple modules to use in a scan.

### List Active Scans

The active scans are listed in the "Active Scans" section.

### Get Scan Status

To get the status of a specific scan, enter the scan ID and click the "Get Scan Status" button.

### List Scan History

The scan history is listed in the "Scan History" section.

### Export Scan Results

To export the results of a completed scan, enter the scan ID and click the "Export as CSV" or "Export as JSON" button.

### Import API Keys

To import an API key for a module, enter the API key and click the "Import API Key" button.

### Export API Keys

The exported API keys are listed in the "API Keys" section.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](../LICENSE) file for details.

## Building and Serving the Production Version

To build the React app for production, run the following command:

```bash
npm run build
```

This will create a `build` directory inside the `client` directory with the production build of the React app.

To serve the production version of the React app, run the following command:

```bash
npm start
```

This will start the Express.js server and serve the static files from the `client/build` directory.

## Integrating the Spiderfoot Logo

To integrate the Spiderfoot logo in the React web app, follow these steps:

1. Add the Spiderfoot logo image file to the `client/src` directory.
2. Import the logo image in the `App.js` file:

```javascript
import logo from './logo.png';
```

3. Add the logo image to the JSX in the `App.js` file:

```javascript
<img src={logo} alt="Spiderfoot Logo" />
```

This will display the Spiderfoot logo in the React web app.
