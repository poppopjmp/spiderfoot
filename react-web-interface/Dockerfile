# Use a Node.js base image
FROM node:16

# Set the working directory
WORKDIR /app

# Copy the package.json and package-lock.json files to the container
COPY ./client /app

# Install the dependencies for the main project
RUN npm install --prefix /app

# Build the React app
RUN npm run build --prefix /app

# Install a simple HTTP server to serve the React app
RUN npm install -g serve

# Serve the React app
CMD ["serve", "-s", "build"]
