# standard library imports
from datetime import timedelta, datetime

# airflow libraries
from airflow import DAG
from airflow.utils.task_group import TaskGroup
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.utils.email import send_email
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def send_failure_email(context):
    subject = f"Airflow Task Failure: {context['task_instance'].task_id}"
    html_content = f"""
    <h3>Task Failed</h3>
    <p><strong>DAG:</strong> {context['dag'].dag_id}</p>
    <p><strong>Task:</strong> {context['task_instance'].task_id}</p>
    <p><strong>Execution Time:</strong> {context['execution_date']}</p>
    <p><strong>Log URL:</strong> <a href="{context['task_instance'].log_url}">View Logs</a></p>
    """
    send_email(to="plunkett.ryanj@gmail.com", subject=subject, html_content=html_content)


def success_email(context):
    subject = f"Airflow Task Success: {context['task_instance'].task_id}"
    html_content = f"""
    <h3>Task Succeeded</h3>
    <p><strong>DAG:</strong> {context['dag'].dag_id}</p>
    <p><strong>Task:</strong> {context['task_instance'].task_id}</p>
    <p><strong>Execution Time:</strong> {context['execution_date']}</p>
    <p><strong>Log URL:</strong> <a href="{context['task_instance'].log_url}">View Logs</a></p>
    """
    send_email(to="plunkett.ryanj@gmail.com", subject=subject, html_content=html_content)


def short_circuit_email(context):
    subject = f"Airflow Task Skipped: {context['task_instance'].task_id}"
    html_content = f"""
    <h3>No Data Available</h3>
    <p><strong>DAG:</strong> {context['dag'].dag_id}</p>
    <p><strong>Task:</strong> {context['task_instance'].task_id}</p>
    <p><strong>Execution Time:</strong> {context['execution_date']}</p>
    <p><strong>Log URL:</strong> <a href="{context['task_instance'].log_url}">View Logs</a></p>
    """
    send_email(to="plunkett.ryanj@gmail.com", subject=subject, html_content=html_content)


dag_args = {
    'owner': 'airflow',
    'start_date': datetime(2026, 9, 28),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=1),
    'email': 'plunkett.ryanj@gmail.com',
    'email_on_failure': True
}

dag = DAG(
    dag_id='baseball_db_table_load',
    description='ETL Pipeline to load the tables used for analysis in the baseball project',
    default_args=dag_args,
    schedule_interval='0 22 * * *',  # Run daily at 22:00,
    max_active_runs=1,
    on_failure_callback=send_failure_email,
    tags=['baseball'],
)

with dag:
    start = DummyOperator(task_id='start')

    evaluate_data_availability = BranchPythonOperator(
        task_id='evaluate_data_availability',
        python_callable=lambda: 'success_path',  # Placeholder for actual data availability check
        op_kwargs={
            'success_path': 'load_statcast_data_staging',
            'short_circuit_path': 'end'
        },
        on_failure_callback=send_failure_email,
        on_success_callback=success_email,
    )

    
    load_statcast_data_staging = BashOperator(
        task_id='load_statcast_data_staging',
        bash_command='python /c/Users/Ryan Plunkett/VSC/baseball/main.py --start {{ ds }} --end {{ ds }} --secrets /c/Users/Ryan Plunkett/VSC/baseball/secrets.yaml',
        on_failure_callback=send_failure_email,
        on_success_callback=success_email,
    )

    end = DummyOperator(task_id='end', trigger_rule=TriggerRule.ALL_DONE)

    start >> evaluate_data_availability >> load_statcast_data_staging >> end
    start >> evaluate_data_availability >> end