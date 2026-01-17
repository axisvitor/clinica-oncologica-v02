import os
import subprocess
import yaml

def update_cloud_run_tasks_config():
    # Define the specific variables for Cloud Tasks
    task_config = {
        "TASK_QUEUE_PROVIDER": "cloud_tasks",
        "CLOUD_TASKS_QUEUE": "hormonia-tasks",
        "CLOUD_TASKS_LOCATION": "us-central1",
        "CLOUD_TASKS_PROJECT_ID": "woven-framework-484323-n7",
        "CLOUD_TASKS_SERVICE_URL": "https://clinica-api-217549452180.us-central1.run.app",
        "CLOUD_TASKS_AUDIENCE": "https://clinica-api-217549452180.us-central1.run.app"
    }
    
    temp_yaml = "tasks_config.yaml"
    
    with open(temp_yaml, 'w') as f:
        yaml.dump(task_config, f, default_flow_style=False)
    
    cmd = [
        "gcloud", "run", "services", "update", "clinica-api",
        "--env-vars-file", temp_yaml,
        "--region", "us-central1",
        "--project", "woven-framework-484323-n7",
        "--quiet"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    finally:
        if os.path.exists(temp_yaml):
            os.remove(temp_yaml)

if __name__ == "__main__":
    try:
        update_cloud_run_tasks_config()
        print("Successfully enabled Cloud Tasks configuration.")
    except Exception as e:
        print(f"Error: {e}")
