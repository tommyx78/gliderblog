module.exports = {
  apps: [{
    name: "gliderblog",
    // Use python3 to execute the uvicorn module
    script: "venv/bin/python3",
    // Command line arguments for uvicorn
    args: "-m uvicorn myweb:app --host 0.0.0.0 --port 7979",
    // Number of instances (use 1 for fork mode, or "max" for cluster mode)
    instances: 1,           
    // Automatically restart the application if it crashes
    autorestart: true,      
    // Disable file watching in production to save resources
    watch: false,           
    // Force restart if memory usage exceeds this limit
    max_memory_restart: '500M', 
    // Default environment variables
    env: {
      NODE_ENV: "development",
      PYTHONUNBUFFERED: "1" // Ensures python output is sent straight to terminal/logs
    },
    // Production specific environment variables
    env_production: {
      NODE_ENV: "production",
      PYTHONUNBUFFERED: "1"
    },
    // Log file locations
    error_file: "./logs/err.log",
    out_file: "./logs/out.log",
    // Timestamp format for log entries
    log_date_format: "YYYY-MM-DD HH:mm:ss"
  }]
};