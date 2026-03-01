import subprocess

def run_all_jobs():
    # Get list of all jobs
    cmd_list = ["gcloud", "scheduler", "jobs", "list", "--location", "us-central1", "--format=value(ID)"]
    result = subprocess.run(cmd_list, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error listing jobs: {result.stderr}")
        return

    jobs = result.stdout.strip().split('\n')
    
    print(f"Found {len(jobs)} jobs. Triggering execution...")
    
    for job in jobs:
        if not job: continue
        print(f"Running job: {job}")
        # Run async to be faster (don't wait for completion)
        subprocess.Popen(
            ["gcloud", "scheduler", "jobs", "run", job, "--location", "us-central1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

if __name__ == "__main__":
    run_all_jobs()
