import boto3
import datetime
import os
from datetime import timezone

# --- CONFIGURATION ---
REGION = "us-east-1"
DRY_RUN = False  # Set to False to actually delete resources
SNAPSHOT_MAX_AGE_DAYS = 30

def load_env():
    """Simple manual loader for .env file if python-dotenv is not available."""
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    # Remove quotes if present
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars

# Load credentials from .env
env = load_env()
session = boto3.Session(
    aws_access_key_id=env.get('aws_access_key_id'),
    aws_secret_access_key=env.get('aws_secret_access_key'),
    region_name=REGION
)
ec2 = session.client('ec2')

def cleanup_ebs_volumes():
    print("\n--- Checking Unattached EBS Volumes ---")
    volumes = ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])['Volumes']
    for vol in volumes:
        print(f"Found: {vol['VolumeId']} ({vol['Size']} GiB)")
        if not DRY_RUN:
            ec2.delete_volume(VolumeId=vol['VolumeId'])
            print(f"Deleted: {vol['VolumeId']}")

def cleanup_ec2_instances():
    print("\n--- Checking Stopped EC2 Instances ---")
    reservations = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['stopped']}])['Reservations']
    for res in reservations:
        for inst in res['Instances']:
            print(f"Found: {inst['InstanceId']}")
            if not DRY_RUN:
                ec2.terminate_instances(InstanceIds=[inst['InstanceId']])
                print(f"Terminated: {inst['InstanceId']}")

def cleanup_elastic_ips():
    print("\n--- Checking Unused Elastic IPs ---")
    addresses = ec2.describe_addresses()['Addresses']
    for addr in addresses:
        if 'InstanceId' not in addr and 'NetworkInterfaceId' not in addr:
            print(f"Found: {addr['PublicIp']}")
            if not DRY_RUN:
                ec2.release_address(AllocationId=addr.get('AllocationId'))
                print(f"Released: {addr['PublicIp']}")

def cleanup_snapshots():
    print(f"\n--- Checking Old Snapshots (> {SNAPSHOT_MAX_AGE_DAYS} days) ---")
    snapshots = ec2.describe_snapshots(OwnerIds=['self'])['Snapshots']
    now = datetime.datetime.now(timezone.utc)
    for snap in snapshots:
        age_days = (now - snap['StartTime']).days
        if age_days > SNAPSHOT_MAX_AGE_DAYS:
            print(f"Found: {snap['SnapshotId']} (Age: {age_days} days)")
            if not DRY_RUN:
                ec2.delete_snapshot(SnapshotId=snap['SnapshotId'])
                print(f"Deleted: {snap['SnapshotId']}")

def main():
    if not env.get('aws_access_key_id') or not env.get('aws_secret_access_key'):
        print("Warning: AWS credentials not found in .env file.")
    
    print(f"AWS Cleanup starting in {REGION} (DRY_RUN={DRY_RUN})")
    
    cleanup_ebs_volumes()
    cleanup_ec2_instances()
    cleanup_elastic_ips()
    cleanup_snapshots()
    
    print("\nCleanup check finished.")

if __name__ == "__main__":
    main()
