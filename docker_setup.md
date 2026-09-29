# Docker Setup & Phase 1 — Compose Skeleton (Windows / Git Bash)

Continues from `secrets-setup-notes.md`. Covers getting Docker Desktop actually running on Windows (this took real troubleshooting), then standing up ClickHouse and Airflow via `docker-compose.yml`.

---

## Installing Docker Desktop

1. Download from https://www.docker.com/products/docker-desktop
2. Run the installer — choose **"per-user"** install when prompted (vs. system-wide); either works, per-user just doesn't require admin rights for the app itself
3. Installer finishes and closes without auto-launching — this is normal, not a failure. Launch Docker Desktop manually afterward from the Start menu.

### "Engine Stopped" / "Virtualization support not detected"

Hit this on first launch. Diagnosis path, in order:

1. **Check Task Manager → Performance → CPU** for "Virtualization: Enabled/Disabled." If disabled, it needs enabling in BIOS/UEFI (see below). If Task Manager already shows *Enabled* but Docker still complains, the real problem is usually WSL2 (next step), not the CPU setting.

2. **Enabling virtualization in BIOS** (only needed if Task Manager showed Disabled):
   - Restart → repeatedly press the BIOS entry key during boot (`Del`, `F2`, `F10`, or `Esc` — varies by manufacturer)
   - Find **Intel VT-x** / **AMD-V** / **SVM Mode** (often under Advanced, CPU Configuration, or Security menus)
   - Enable → Save & Exit

3. **Check `wsl --status` in PowerShell.** An empty/blank response (no error, no output) means WSL isn't actually installed, even if virtualization is fine — this was the actual root cause here, not the BIOS setting.
   - Fix: open PowerShell **as Administrator**, run:
     ```powershell
     wsl --install
     ```
   - This downloads the WSL2 kernel component and a default distro (Ubuntu). **The progress bar resetting to 0% partway through is normal** — it's moving from "downloading" to "extracting/installing," a separate phase reusing the same UI. Don't assume it's hung unless there's zero Task Manager activity (check the Details tab for `wsl.exe`/`Ubuntu.exe`) for several minutes straight.
   - Reboot when prompted.
   - Re-run `wsl --status` — should now show a default distro name and "Default Version: 2."

4. **Confirm required Windows features are on** (search "Turn Windows features on or off"):
   - Virtual Machine Platform
   - Windows Subsystem for Linux

5. Relaunch Docker Desktop — engine should now show **"Engine running"** (green).

### Firewall prompt on first container start

The first time a container binds a port (e.g. ClickHouse's 8123/9000), Windows Defender Firewall prompts for permission. Check **Private networks** (sufficient for local dev) and Allow access. Unrelated to any actual misconfiguration — just a one-time first-bind prompt.

---

## Phase 1, Step 5 — `docker-compose.yml` with ClickHouse

Created at repo root (not inside `/docker` — that subfolder is reserved for supporting files like custom Dockerfiles or config overrides, and stays empty until one of those is actually needed):

```yaml
services:
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: baseball-clickhouse
    ports:
      - "8123:8123"   # HTTP interface
      - "9000:9000"   # native TCP interface (clickhouse-client, clickhouse-connect)
    volumes:
      - clickhouse_data:/var/lib/clickhouse
    ulimits:
      nofile:
        soft: 262144
        hard: 262144

volumes:
  clickhouse_data:
```

**Why each piece:**
- **Two ports** — 8123 (HTTP, used by `clickhouse-connect` and some GUI tools) and 9000 (native protocol, used by `clickhouse-client`). Both are useful since the ingestion script and manual CLI checks use different ones.
- **Named volume (`clickhouse_data`)** — decouples data from the container's lifecycle. Without it, `docker compose down` wipes the database; with it, the volume persists on the host and gets reattached on `up`, even if the container itself is fully removed and recreated.
- **`ulimits`** — ClickHouse needs a higher file descriptor limit than Docker's default; setting this upfront avoids a confusing error once there are more tables/parts on disk.
- **`latest` tag** — fine to start; worth pinning to a specific version (e.g. `24.8`) later so a future `docker compose pull` doesn't silently change server behavior underneath you.

---

## Step 6 — Verify connectivity and persistence

```bash
docker compose up -d
docker compose ps                    # confirm STATUS shows "Up"
docker exec -it baseball-clickhouse clickhouse-client
```

Lands in an interactive `:) ` prompt. The two startup warnings shown (delay accounting not enabled, clock source not fast) are informational kernel-tuning notes from inside the container's Linux environment — irrelevant for local dev, safe to ignore.

**Persistence test** (the actual point of this step — proving the named volume works):
```sql
CREATE DATABASE test_persist;
exit
```
```bash
docker compose down          # removes container + network, NOT the named volume
docker compose up -d
docker exec -it baseball-clickhouse clickhouse-client --query "SHOW DATABASES"
```
`test_persist` should still be listed — confirmed working. Note that on the second `up`, only the network and container get recreated; the volume isn't touched at all if it already exists, which is exactly the behavior that makes data durable across restarts.

Clean up afterward:
```bash
docker exec -it baseball-clickhouse clickhouse-client --query "DROP DATABASE test_persist"
```

---

## Step 7 — Adding Airflow to the same compose file

Airflow needs more moving parts than ClickHouse: its own metadata database (Postgres), a one-time init step (schema migration + admin user creation), and two long-running services (webserver, scheduler) that share state through that metadata DB.

```yaml
services:
  clickhouse:
    # ...existing service from step 5...

  postgres:
    image: postgres:16
    container_name: baseball-airflow-postgres
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - airflow_postgres_data:/var/lib/postgresql/data

  airflow-init:
    image: apache/airflow:2.10.2
    container_name: baseball-airflow-init
    depends_on:
      - postgres
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    entrypoint: /bin/bash
    command:
      - -c
      - |
        airflow db migrate
        airflow users create \
          --username admin \
          --password admin \
          --firstname Admin \
          --lastname User \
          --role Admin \
          --email admin@example.com

  airflow-webserver:
    image: apache/airflow:2.10.2
    container_name: baseball-airflow-webserver
    depends_on:
      - postgres
      - airflow-init
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    ports:
      - "8080:8080"
    volumes:
      - ./dags:/opt/airflow/dags
    command: webserver

  airflow-scheduler:
    image: apache/airflow:2.10.2
    container_name: baseball-airflow-scheduler
    depends_on:
      - postgres
      - airflow-init
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    volumes:
      - ./dags:/opt/airflow/dags
    command: scheduler

volumes:
  clickhouse_data:
  airflow_postgres_data:
```

**What each service is for:**
- **`postgres`** — Airflow's metadata DB (DAG runs, task state, connections, users). Entirely separate from ClickHouse; different concern, different database by design — never mix analytics data and orchestration metadata in the same store.
- **`airflow-init`** — one-shot container. Runs `airflow db migrate` (schema setup) then creates the first admin login. Expected to exit with status `0` after finishing — showing as `Exited (0)` in `docker compose ps` is correct, not a failure.
- **`airflow-webserver`** — serves the UI on port 8080.
- **`airflow-scheduler`** — parses DAG files and actually triggers task runs. Both webserver and scheduler read/write the same Postgres DB to stay in sync with each other.
- **`./dags:/opt/airflow/dags` volume mount** — maps the repo's local `/dags` folder into the container, so DAG files written locally are picked up without rebuilding the image.
- **No explicit `networks:` block needed** — Compose puts every service in one file on the same default network automatically (`baseball_default`), so Airflow can reach ClickHouse by service name/hostname (`clickhouse:9000`) with zero extra config. This is what makes "Airflow can see ClickHouse" work out of the box.
- **`admin`/`admin` and `airflow`/`airflow` credentials** — fine as placeholders for pure local dev (never leaves localhost), not a pattern to carry into anything shared or deployed later.

```bash
docker compose up -d
```
First run pulls the Airflow image (larger than ClickHouse — expect several minutes), runs migrations, creates the admin user, then starts webserver + scheduler.

---