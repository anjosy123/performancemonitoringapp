# How to Fix Image Loading on Render

## Option 1: Deploy Changes with Context Processor

1. Make sure your `hospital-logo.png` exists in the `static/images/` directory.

2. Add this file to your Git repository:
   ```
   git add static/images/hospital-logo.png
   git add staff_monitor/context_processors.py
   git add staff_monitor/templates/staff_monitor/login.html
   git add performance_monitor/settings.py
   git commit -m "Fix background image with fallback mechanism"
   git push
   ```

3. Deploy to Render (this will happen automatically when you push to your connected repository).

## Option 2: Manual Upload (If Option 1 Doesn't Work)

1. Log in to your Render dashboard
2. Go to your web service
3. Navigate to the "Shell" tab
4. Upload the image directly to the static files location:
   ```bash
   # Create the directory if it doesn't exist
   mkdir -p staticfiles/images/
   
   # Create a simple fallback image using a built-in command
   echo '<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="#0d6efd"/><text x="50%" y="50%" font-family="Arial" font-size="24" text-anchor="middle" fill="white">Hospital Logo</text></svg>' > staticfiles/images/hospital-logo.png
   
   # Alternatively, download an image from a URL
   # curl -o staticfiles/images/hospital-logo.png https://example.com/path/to/image.png
   
   # Or create a temporary PNG hospital logo
   cat > staticfiles/images/hospital_front.JPG << 'EOL'
   <svg width="1200" height="800" xmlns="http://www.w3.org/2000/svg">
     <rect width="1200" height="800" fill="#f8f9fa"/>
     <rect x="400" y="200" width="400" height="400" fill="#0d6efd"/>
     <text x="600" y="400" font-family="Arial" font-size="48" text-anchor="middle" fill="white">Hospital</text>
     <text x="600" y="500" font-family="Arial" font-size="48" text-anchor="middle" fill="white">Building</text>
   </svg>
   EOL
   ```

5. Restart your web service

## Option 3: Modify Your Code Directly on Render

In case both options above don't work, you can directly edit the login.html file on Render:

1. Go to the Shell tab in your web service
2. Run the following command to edit the template:
   ```bash
   nano staticfiles/staff_monitor/templates/staff_monitor/login.html
   ```

3. Find the background CSS rule and change it to:
   ```css
   body {
       background: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.5)),
                   url('/static/images/hospital_front.png')
       /* rest of the CSS remains the same */
   }
   ```

4. Save the file and restart your web service 