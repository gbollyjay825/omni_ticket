const base = process.env.OMNI_DEPLOY_BASE || "/home/amechi/omni-ticket";
const runtimeEnv = `${base}/runtime/env.sh`;

function bashProcess(name, command) {
  return {
    name,
    script: "/bin/bash",
    args: ["-lc", `. "${runtimeEnv}" && ${command}`],
    autorestart: true,
    max_restarts: 10,
    min_uptime: "10s",
    kill_timeout: 10000,
    listen_timeout: 10000,
    env: {
      OMNI_DEPLOY_BASE: base,
    },
  };
}

module.exports = {
  apps: [
    bashProcess(
      "omni-ticket-api",
      `cd "${base}/current/backend" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090`,
    ),
    bashProcess(
      "omni-ticket-worker",
      `cd "${base}/current/backend" && exec .venv/bin/python -m app.worker --interval-seconds \${OMNI_WORKER_INTERVAL_SECONDS:-60} --outbound-limit \${OMNI_WORKER_OUTBOUND_LIMIT:-50}`,
    ),
    bashProcess(
      "omni-ticket-frontend",
      `cd "${base}/current" && exec node infra/scripts/pulse-static-server.mjs`,
    ),
  ],
};
