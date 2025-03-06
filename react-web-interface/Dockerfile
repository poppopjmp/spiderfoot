# Use a Node.js base image
FROM node:18 AS builder

# Set the working directory
WORKDIR /app/client

# Copy the package.json and package-lock.json files to the container
COPY ./client/package*.json ./

# Install the dependencies for the main project
RUN npm install
RUN npm install react-router-dom@^6.0.0
# Copy the rest of the client files
COPY ./client .

# Build the React app

COPY ./src .

RUN npm run build
# Use a smaller base image for the final stage
FROM nginx:alpine

# Copy the build output to the nginx html directory
COPY --from=builder /app/client/build /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
