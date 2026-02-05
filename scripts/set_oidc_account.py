import os
import subprocess
import yaml

def set_oidc_service_account():
    # Set the OIDC service account email
    # Using the default compute service account which typically runs the Cloud Run service
    # and has permissions (if granted) to invoke it.
    config = {
        "CLOUD_TASKS_OIDC_SERVICE_ACCOUNT": "217549452180-compute@developer.gserviceaccount.com"
    }
    
    temp_yaml = "oidc_config.yaml"
    
    with open(temp_yaml, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
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
        set_oidc_service_account()
        print("Successfully set CLOUD_TASKS_OIDC_SERVICE_ACCOUNT.")
    except Exception as e:
        print(f"Error: {e}")
