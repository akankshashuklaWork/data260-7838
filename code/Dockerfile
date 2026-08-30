# Use a small Nginx image to serve the static web application.
FROM nginx:alpine

# Remove the sample website included with Nginx.
RUN rm -rf /usr/share/nginx/html/*

# Copy only the shared web application into the image.
COPY code/web_application/index.html /usr/share/nginx/html/index.html
COPY code/web_application/styles.css /usr/share/nginx/html/styles.css
COPY code/web_application/script.js /usr/share/nginx/html/script.js

# Nginx listens on port 80 inside the container.
EXPOSE 80

# Keep Nginx running in the foreground.
CMD ["nginx", "-g", "daemon off;"]
