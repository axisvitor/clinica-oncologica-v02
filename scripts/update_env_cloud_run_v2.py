import os
import subprocess
import yaml

def parse_env_file(filepath):
    env_vars = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                env_vars[key.strip()] = value.strip()
    return env_vars

def update_cloud_run(env_vars):
    # Write to a temporary YAML file
    # This avoids all shell escaping issues
    temp_yaml = "env_vars_temp.yaml"
    
    # Filter valid vars
    valid_vars = {k: str(v) for k, v in env_vars.items() if k and v}
    
    with open(temp_yaml, 'w') as f:
        yaml.dump(valid_vars, f, default_flow_style=False)
    
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
        # Securely remove the temp file
        if os.path.exists(temp_yaml):
            os.remove(temp_yaml)

if __name__ == "__main__":
    try:
        env_vars = parse_env_file("backend-hormonia/.env")
        update_cloud_run(env_vars)
        print("Successfully updated Cloud Run environment variables using YAML file.")
    except Exception as e:
        print(f"Error: {e}")
