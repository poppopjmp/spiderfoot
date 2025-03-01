# Use a Node.js base image
FROM node:14

WORKDIR /app
# Set the working directory
# Copy the package.json and package-lock.json files to the container
COPY . .
WORKDIR /app/react-web-interface
# Install the dependencies
RUN npm install

# Copy the rest of the application code to the container

# Build the React app
RUN npm run build

# Install a simple HTTP server to serve the React app
RUN npm install -g serve

# Serve the React app
CMD ["serve", "-s", "build"]
