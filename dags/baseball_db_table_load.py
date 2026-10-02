import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from airflow.utils.email import send_email
from airflow.utils.trigger_rule import TriggerRule

REPO = "/opt/airflow/repo"  # where the repo is mounted in the container
ALERT_EMAIL = os.environ.get("ALERT_EMAIL")
LOOKBACK_DAYS = 7


def send_failure_email(context):
    if not ALERT_EMAIL:
        return
    ti = context["task_instance"]
    send_email(
        to=ALERT_EMAIL,
        subject=f"Airflow Task Failure: {ti.task_id}",
        html_content=(
            f"<h3>Task Failed</h3>"
            f"<p><strong>DAG:</strong> {context['dag'].dag_id}</p>"
            f"<p><strong>Task:</strong> {ti.task_id}</p>"
            f"<p><a href=\"{ti.log_url}\">View Logs</a></p>"
        ),
    )


def choose_path(**context):
    # Placeholder for a real availability check (e.g. MLB schedule has games).
    return "ingest_statcast"  # or "end" to skip the run


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 3,  # safe: the load is delete-then-insert, so retries can't duplicate rows
    "retry_delay": timedelta(minutes=1),
    "on_failure_callback": send_failure_email,
}

with DAG(
    dag_id="baseball_db_table_load",
    description="Load Statcast into raw, then build and test staging with dbt",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 9, 28, tz="America/Los_Angeles"),
    schedule='0 6 * * *',
    catchup=False,
    max_active_runs=1,
    tags=["baseball"],
) as dag:
    start = EmptyOperator(task_id="start")

    check_data = BranchPythonOperator(
        task_id="evaluate_data_availability",
        python_callable=choose_path,
    )

    ingest = BashOperator(
        task_id="ingest_statcast",
        bash_command=(
            f"cd {REPO} && python main.py "
            f"--start {{{{ macros.ds_add(ds, -{LOOKBACK_DAYS}) }}}} --end {{{{ ds }}}}"
        ),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {REPO}/dbt/baseball && /opt/airflow/dbt-venv/bin/dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {REPO}/dbt/baseball && /opt/airflow/dbt-venv/bin/dbt test",
    )

    end = EmptyOperator(
        task_id="end", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )

    start >> check_data >> [ingest, end]
    ingest >> dbt_run >> dbt_test >> end