# Use a Node.js base image
FROM node:14

WORKDIR /app
# Set the working directory
# Copy the package.json and package-lock.json files to the container
COPY . .

# Install the dependencies for the main project
RUN npm install

WORKDIR /app/client 

# Install the dependencies for the client project
RUN npm install

WORKDIR /app

# Build the React app
RUN npm run build

# Install a simple HTTP server to serve the React app
RUN npm install -g serve

# Serve the React app
CMD ["serve", "-s", "build"]
