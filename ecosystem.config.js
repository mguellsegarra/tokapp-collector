module.exports = {
  apps: [
    {
      name: "tokapp-collector",
      script: ".venv/bin/tokapp-collector",
      args: "--env-file .env run",
      cwd: __dirname,
      interpreter: "none",
      autorestart: true,
      restart_delay: 15000,
      max_restarts: 10,
      watch: false,
      time: true,
    },
  ],
};
