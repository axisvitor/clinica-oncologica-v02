import os
import subprocess

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
                
                # Handle potential multiline keys like private keys if they are single-lined in the file
                # If your .env has actual newlines inside values, simple line reading breaks.
                # Assuming standard .env format where newlines are escaped as \n
                env_vars[key.strip()] = value.strip()
    return env_vars

def update_cloud_run(env_vars):
    # Construct the env vars string for gcloud
    # Format: KEY1=VALUE1,KEY2=VALUE2
    # We need to escape commas in values if any, but gcloud might not like that easily.
    # A better way is to pass them one by one or use a file, but `update-env-vars` takes a list.
    
    # Filter out empty keys
    valid_vars = {k: v for k, v in env_vars.items() if k and v}
    
    env_pairs = []
    for k, v in valid_vars.items():
        # Escape commas as they are delimiters in gcloud command
        # v = v.replace(',', '\\,') 
        # Actually gcloud format is tricky with commas. 
        # Let's try to set them. 
        env_pairs.append(f"{k}={v}")

    env_string = ",".join(env_pairs)
    
    cmd = [
        "gcloud", "run", "services", "update", "clinica-api",
        "--update-env-vars", env_string,
        "--region", "us-central1",
        "--project", "woven-framework-484323-n7",
        "--quiet"
    ]
    
    # Print command for debugging (masking secrets)
    # print("Running update...")
    
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    try:
        env_vars = parse_env_file("backend-hormonia/.env")
        update_cloud_run(env_vars)
        print("Successfully updated Cloud Run environment variables.")
    except Exception as e:
        print(f"Error: {e}")
