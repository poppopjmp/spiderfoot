# Use a Node.js base image
FROM node:18

# Set the working directory
WORKDIR /app/client

# Copy the package.json and package-lock.json files to the container
COPY ./client /app/client

# Install the dependencies for the main project
RUN npm install --prefix /app/client

# Build the React app
RUN npm run build --prefix /app/client

# Install a simple HTTP server to serve the React app
RUN npm install -g serve

# Serve the React app
CMD ["serve", "-s", "client/build"]
